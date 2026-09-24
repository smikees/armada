"""Real capability version-scan + update, via the Claude Code CLI.

ARMADA can genuinely see/update only capabilities registered with the CLI (`claude plugin`,
`claude mcp`). It reconciles those into the realm's capability list with real installed/latest
versions and applies updates with `claude plugin update`. Capabilities managed elsewhere (the
desktop app's plugin/connector layer) aren't visible here — we simply leave them untouched.

Everything here is best-effort and never raises out: a missing CLI or an offline registry just
means "nothing to report", so a scan can't break the app or a run.
"""
from __future__ import annotations
import json
import re
import subprocess
from pathlib import Path

from .engine.claude import ClaudeEngine, _NO_WINDOW
from . import util
import logging
from .util import swallowed
log = logging.getLogger(__name__)


def _lp():
    try:
        return ClaudeEngine()._launcher()
    except Exception:  # noqa
        log.debug('_lp: failed; returning a fallback', exc_info=True)
        return None


def _run(args, timeout=60):
    lp = _lp()
    if not lp:
        return 1, ""
    try:
        r = subprocess.run(lp + args, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace", creationflags=_NO_WINDOW)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception:  # noqa
        swallowed(log, '_run: failed; returning a fallback')
        return 1, ""


def _norm_plugin(d: dict) -> dict:
    """Normalise one plugin record from `claude plugin list [--available] --json` (shape-tolerant)."""
    name = d.get("name") or d.get("plugin") or d.get("id") or ""
    version = d.get("version") or d.get("installedVersion") or d.get("installed") or ""
    latest = (d.get("latestVersion") or d.get("latest") or d.get("availableVersion")
              or d.get("available") or "")
    if isinstance(latest, bool):   # some shapes use available:true without a version
        latest = ""
    return {"name": str(name), "version": str(version or ""), "latest": str(latest or ""),
            "marketplace": str(d.get("marketplace") or d.get("source") or "")}


def list_plugins() -> list:
    """Installed plugins with any available (latest) version — real data from the CLI, or []."""
    rc, out = _run(["plugin", "list", "--available", "--json"])
    if rc != 0 or not out.strip():
        rc, out = _run(["plugin", "list", "--json"])
    try:
        data = json.loads(out)
    except Exception:  # noqa
        swallowed(log, 'list_plugins: failed; returning a fallback')
        return []
    rows = data if isinstance(data, list) else (data.get("plugins") or data.get("installed") or [])
    return [_norm_plugin(d) for d in rows if isinstance(d, dict) and (d.get("name") or d.get("id"))]


def list_mcp() -> list:
    """Configured MCP servers from the CLI as [{name, remote, command}].

    `remote` = the entry is a URL (http/sse transport = a Connector); otherwise it's a local
    stdio command (= an Extension).

    `command` is the rest of the line, and keeping it is the point. It used to be read for the
    "://" test and thrown away, which left a discovered server as a bare name — and a bare name
    is not enough to say what something IS. `filesystem` could then only be guessed at, against
    every server in the MCP registry with that generic word in it; its command line says plainly
    that it is Anthropic's Claude Desktop extension and settles the question outright.
    """
    rc, out = _run(["mcp", "list"])
    if rc != 0:
        return []
    servers = []
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln or ":" not in ln or ln.lower().startswith(("no ", "checking", "usage")):
            continue
        name, detail = ln.split(":", 1)
        name = name.strip()
        # Every real row is "<name>: <command> - <status>". Requiring the status separator is what
        # lets the name contain spaces safely, and it must: Claude's own connectors are all called
        # things like "claude.ai Google Drive", so rejecting spaces silently dropped every one of
        # them — including the remote URL that says what each actually is.
        if not name or " - " not in detail:
            continue
        cmd = detail.split(" - ", 1)[0].strip()  # drop the trailing "- ✓ Connected" status
        servers.append({"name": name, "remote": "://" in cmd, "command": cmd})
    return servers


# A Claude Desktop extension unpacks under ".../Claude Extensions/<bundle-id>/...", and the bundle
# id carries its own provenance: ant.dir.<host>.<publisher>.<name>. That is a real answer to "where
# did this come from" — better than anything a name search could produce, and available for free on
# a line we were already reading.
_EXT_DIR_RE = re.compile(r"Claude Extensions[\\/]+([A-Za-z0-9._-]+)")


def extension_identity(command: str) -> dict:
    """{id, publisher, name} for a Claude Desktop extension command, or {} if it isn't one."""
    m = _EXT_DIR_RE.search(str(command or ""))
    if not m:
        return {}
    bid = m.group(1)
    out = {"id": bid, "publisher": "", "name": ""}
    parts = bid.split(".")
    # ant.dir.<host>.<publisher>.<name...> — the shape Anthropic's own directory uses. Anything
    # else keeps its id and claims no publisher rather than guessing one out of a dotted string.
    if len(parts) >= 5 and parts[0] == "ant" and parts[1] == "dir":
        out["publisher"] = parts[3]
        out["name"] = ".".join(parts[4:])
    return out


def _discovered_provenance(command: str) -> dict:
    """What the command line proves about a discovered server.

    `command` is kept on every discovered item because it is the only durable evidence of what the
    thing actually is. Where it identifies a Claude Desktop extension we can also name the source
    and the publisher outright, and `identified` marks the question CLOSED — nothing downstream
    should then go looking for a catalogue entry that resembles the name.
    """
    out = {"command": str(command or "")}
    ext = extension_identity(command)
    if ext:
        out["origin"] = "Claude Desktop extension"
        out["scope"] = "Claude Desktop extension"
        out["extension_id"] = ext["id"]
        out["identified"] = True
        if ext["publisher"]:
            out["made_by"] = ext["publisher"].title()
    return out


def _norm(s) -> str:
    import re
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def reconcile(toolkit: dict, plugins: list, mcp: list, *, discover: bool = False) -> bool:
    """Write real installed/latest versions onto the toolkit items this realm already has.

    Pure (mutates the dict), returns True if anything changed. Testable offline.

    `discover` is off by default, and that is the point. This used to append every CLI-known
    plugin and MCP server into whichever realm happened to be open when someone pressed "check
    for version updates" — but the CLI is machine-wide and a realm is not. Installing something
    while working in one realm made it appear, unasked, in the capability list of every other
    realm you later opened: a list that is supposed to be the record of what YOU allowed in here.

    So the realm catalogue is now only ever added to deliberately, from the Catalogue tab. What
    the CLI knows is still read — it is what tells you a capability is already on this computer,
    and it is where real version numbers come from — it just doesn't file itself.
    """
    changed = False
    by_key = {}
    for kind in ("connectors", "extensions", "skills", "plugins"):
        for it in (toolkit.get(kind) or []):
            for k in (_norm(it.get("id")), _norm(it.get("name"))):
                if k:
                    by_key[k] = it
    # plugins: set real version/latest on matches; add unknown ones under 'plugins'
    plug_list = toolkit.setdefault("plugins", [])
    have = {_norm(it.get("id")) for it in plug_list} | {_norm(it.get("name")) for it in plug_list}
    for p in plugins:
        it = by_key.get(_norm(p["name"]))
        if it is not None:
            if p["version"] and it.get("version") != p["version"]:
                it["version"] = p["version"]; changed = True
            if p["latest"] and p["latest"] != p["version"]:
                if it.get("latest") != p["latest"]:
                    it["latest"] = p["latest"]
                    it.setdefault("update_info", "A newer version is available from the marketplace.")
                    changed = True
            elif it.get("latest"):
                it.pop("latest", None); it.pop("update_info", None); changed = True
        elif discover and _norm(p["name"]) not in have:
            item = {"id": p["name"], "name": p["name"], "icon": "cap-plugin", "scope": "Claude plugin",
                    "status": "connected", "source": "3p", "discovered": True, "version": p["version"] or "1.0.0"}
            if p["latest"] and p["latest"] != p["version"]:
                item["latest"] = p["latest"]; item["update_info"] = "A newer version is available."
            plug_list.append(item); have.add(_norm(p["name"])); changed = True
    # mcp servers: local stdio -> Extensions (runs code here); remote http/sse -> Connectors (outside service).
    # Same MCP primitive, filed by where it runs. `mcp` items are {name, remote} (str tolerated for back-compat).
    conns = toolkit.setdefault("connectors", [])
    exts = toolkit.setdefault("extensions", [])
    chave = {_norm(it.get("id")) for it in conns} | {_norm(it.get("name")) for it in conns}
    ehave = {_norm(it.get("id")) for it in exts} | {_norm(it.get("name")) for it in exts}
    for m in mcp:
        name = m["name"] if isinstance(m, dict) else str(m)
        remote = bool(m.get("remote")) if isinstance(m, dict) else False
        nk = _norm(name)
        cmd = (m.get("command") or "") if isinstance(m, dict) else ""
        prov = _discovered_provenance(cmd)
        # The server is already in this realm: bring what we have just learned to the record we
        # already hold, rather than skipping it. Everything here was discovered as a bare name
        # before the command was kept, so the realms that most need identifying are exactly the
        # ones an add-only pass would never touch.
        known = by_key.get(nk)
        if known is not None:
            for k, v in prov.items():
                # Never overwrite a source the owner chose in the Catalogue, or a name they see.
                if k in ("origin", "scope", "made_by") and known.get("catalogue_key"):
                    continue
                if known.get(k) != v:
                    known[k] = v
                    changed = True
            continue
        if not discover or nk in chave or nk in ehave:
            continue
        if remote:
            conns.append({"id": name, "name": name, "icon": "cap-connector",
                          "scope": "Remote MCP server", "status": "connected", "source": "3p",
                          "discovered": True, "runs": "service", "touch": ["network"], **prov})
            chave.add(nk)
        else:
            exts.append({"id": name, "name": name, "icon": "cap-extension",
                         "scope": "Local MCP server", "status": "connected", "source": "3p",
                         "discovered": True, "runs": "code", "touch": ["files", "network"], **prov})
            ehave.add(nk)
        changed = True
    return changed


def scan(realm_root) -> dict:
    """Scan CLI-known capabilities and write real installed/latest into realm.json. Best-effort."""
    try:
        plugins, mcp = list_plugins(), list_mcp()
        rp = Path(realm_root) / "realm.json"
        with util.file_lock(rp):
            js = json.loads(rp.read_text(encoding="utf-8-sig"))
            tk = js.setdefault("toolkit", {})
            if reconcile(tk, plugins, mcp):
                util.write_json_atomic(rp, js)
            updates = sum(1 for kind in ("connectors", "extensions", "skills", "plugins")
                          for it in (tk.get(kind) or []) if it.get("latest"))
        return {"ok": True, "plugins": len(plugins), "mcp": len(mcp), "updates": updates}
    except Exception as e:  # noqa
        swallowed(log, 'scan: failed; error returned to the caller')
        return {"ok": False, "error": str(e)[:200]}


def apply_plugin_update(name: str) -> dict:
    """Really update a CLI-installed plugin (`claude plugin update <name>`)."""
    rc, out = _run(["plugin", "update", name], timeout=180)
    return {"ok": rc == 0, "out": out.strip()[:1500]}
