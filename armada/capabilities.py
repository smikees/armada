"""Who may use which capability.

One rule, stated once, so every other part of the app can ask instead of deciding for itself:

* **The realm holds the catalogue.** Everything discovered, installed or imported lands at realm
  level and nowhere else. A capability existing is not a capability anyone can use.
* **A coordinator may use all of it.** If a realm has a PM, that role is the one that sees across
  the whole realm, so granting it everything is the honest description of the job rather than a
  shortcut. A realm with no coordinator has no agent with blanket access — nobody inherits it.
* **Every other agent may use only what it has been granted**, either by the owner mapping it on
  the Capabilities page or by approving a request the agent made in a thread.
* **Every agent can SEE the whole catalogue.** Discovery is the point — an agent that can't know a
  tool exists can't ask for it. Seeing is not using.

The inversion that matters: before this, an empty agent toolkit meant *inherit everything*, and
the only thing that could stop an agent was a capability switched off for the entire realm. Empty
now means **nothing**, and a grant is a positive act. That way the question "what can this agent
reach" is answered by a list you can read, rather than by the absence of a prohibition.

**What is actually enforced.** Connectors and extensions are MCP servers, so an ungranted one is
withheld by denying its `mcp__<id>` tools at the engine — real enforcement, not advice. Skills and
plugins have no equivalent per-call handle, so for those a grant controls what the agent is *told
it has*; an agent that goes looking for an ungranted skill is not stopped by this module. Said
plainly here because the difference decides how much weight the grant list can carry.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import util
import logging
from .util import swallowed
log = logging.getLogger(__name__)

KINDS = ("connectors", "extensions", "skills", "plugins")

# Kinds backed by an MCP server, and therefore the ones a grant can actually enforce.
MCP_KINDS = ("connectors", "extensions", "plugins")

REQUESTS_DIR = "capability-requests"


def _now() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _read(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:  # noqa — a missing or broken file reads as empty, never as an error
        swallowed(log, '_read: failed; returning a fallback')
        return {}


def cap_key(cap) -> str:
    """The identity of a capability, for comparing across realm and agent lists.

    Ids are what discovery writes and what the engine matches on, so the id wins when present;
    a hand-added entry may only have a name. Compared case-insensitively because these are server
    names typed by people.
    """
    if isinstance(cap, str):
        return cap.strip().lower()
    return str((cap or {}).get("id") or (cap or {}).get("name") or "").strip().lower()


# --------------------------------------------------------------------------- the catalogue

def catalogue(realm_root) -> dict:
    """{kind: [cap, ...]} — everything this realm knows about."""
    tk = _read(Path(realm_root) / "realm.json").get("toolkit") or {}
    result = {k: list(tk.get(k) or []) for k in KINDS}
    from .connector_runtime import is_provider_placeholder
    result["connectors"] = [c for c in result["connectors"] if not is_provider_placeholder(c)]
    return result


def catalogue_flat(realm_root) -> list:
    """[(kind, cap), ...] across every kind, in a stable order."""
    cat = catalogue(realm_root)
    return [(k, c) for k in KINDS for c in cat[k]]


def find(realm_root, cap_id: str):
    """(kind, cap) for a capability in the realm catalogue, or (None, None)."""
    want = cap_key(cap_id)
    for kind, cap in catalogue_flat(realm_root):
        if cap_key(cap) == want:
            return kind, cap
    return None, None


def realm_enabled(cap) -> bool:
    """Is this capability switched on for the realm at all? A realm-level off beats any grant."""
    return (cap or {}).get("enabled", True) is not False


# --------------------------------------------------------------------------- agents and grants

def _agent(realm_root, agent) -> dict:
    """Accept an agent id or an already-loaded agent dict."""
    if isinstance(agent, dict):
        return agent
    return _read(Path(realm_root) / "agents" / str(agent) / "agent.json")


def is_coordinator(agent) -> bool:
    return bool((agent or {}).get("coordinator"))


def has_coordinator(realm_root) -> bool:
    adir = Path(realm_root) / "agents"
    for ap in sorted(adir.glob("*")) if adir.is_dir() else []:
        if is_coordinator(_read(ap / "agent.json")):
            return True
    return False


def grants(realm_root, agent) -> dict:
    """{kind: [cap, ...]} the agent has been explicitly granted (its own toolkit)."""
    tk = (_agent(realm_root, agent).get("toolkit") or {})
    return {k: list(tk.get(k) or []) for k in KINDS}


def granted_keys(realm_root, agent) -> set:
    return {cap_key(c) for k in KINDS for c in grants(realm_root, agent)[k] if cap_key(c)}


def usable(realm_root, agent) -> dict:
    """{kind: [cap, ...]} the agent may actually use, resolved against the realm catalogue.

    Returns realm entries rather than the agent's copies, so the description, icon and status an
    agent sees are the realm's current ones and a stale grant can't misreport them.
    """
    a = _agent(realm_root, agent)
    cat = catalogue(realm_root)
    if is_coordinator(a):
        return {k: [c for c in cat[k] if realm_enabled(c)] for k in KINDS}
    keys = granted_keys(realm_root, a)
    return {k: [c for c in cat[k] if realm_enabled(c) and cap_key(c) in keys] for k in KINDS}


def visible(realm_root, agent) -> dict:
    """{kind: [cap, ...]} the agent may KNOW ABOUT. The whole enabled catalogue, always.

    An agent that cannot see a tool exists cannot ask for it, and then the owner is the only one
    who can ever notice the gap.
    """
    cat = catalogue(realm_root)
    return {k: [c for c in cat[k] if realm_enabled(c)] for k in KINDS}


def requestable(realm_root, agent) -> dict:
    """{kind: [cap, ...]} visible but not usable — exactly what an agent could ask for."""
    use = {cap_key(c) for k in KINDS for c in usable(realm_root, agent)[k]}
    return {k: [c for c in visible(realm_root, agent)[k] if cap_key(c) not in use] for k in KINDS}


def may_use(realm_root, agent, cap_id) -> bool:
    want = cap_key(cap_id)
    return any(cap_key(c) == want for k in KINDS for c in usable(realm_root, agent)[k])


# --------------------------------------------------------------------------- changing grants

def grant(realm_root, agent_id: str, cap_id: str, *, via: str = "user", thread: str = "") -> dict:
    """Let an agent use a realm capability.

    `via` records how the grant happened ("user" from the Capabilities page, "thread" from an
    approved in-conversation request) and `thread` which conversation it came from — that pairing
    is what lets a thread show which of its capabilities are new to the agent rather than ones it
    already had.
    """
    agent_id = util.safe_seg(agent_id, "agent")
    kind, cap = find(realm_root, cap_id)
    if not kind:
        return {"ok": False, "error": f"No capability '{cap_id}' in this realm."}
    if not realm_enabled(cap):
        return {"ok": False, "error": f"'{cap.get('name') or cap_id}' is switched off for the whole realm."}

    ap = Path(realm_root) / "agents" / agent_id / "agent.json"
    if not ap.exists():
        return {"ok": False, "error": f"No agent '{agent_id}'."}
    with util.file_lock(ap):
        a = util.read_json_state(ap)
        if is_coordinator(a):
            return {"ok": True, "already": True, "coordinator": True,
                    "detail": "The coordinator can already use everything in the realm."}
        tk = a.setdefault("toolkit", {})
        lst = tk.setdefault(kind, [])
        if any(cap_key(c) == cap_key(cap) for c in lst):
            return {"ok": True, "already": True}
        lst.append({"id": cap.get("id", ""), "name": cap.get("name") or cap.get("id", ""),
                    "granted_at": _now(), "granted_via": via,
                    **({"granted_thread": thread} if thread else {})})
        util.write_json_atomic(ap, a)
    return {"ok": True, "agent": agent_id, "kind": kind,
            "capability": cap.get("name") or cap.get("id"), "via": via, "thread": thread}


def revoke(realm_root, agent_id: str, cap_id: str) -> dict:
    agent_id = util.safe_seg(agent_id, "agent")
    ap = Path(realm_root) / "agents" / agent_id / "agent.json"
    if not ap.exists():
        return {"ok": False, "error": f"No agent '{agent_id}'."}
    want = cap_key(cap_id)
    with util.file_lock(ap):
        a = util.read_json_state(ap)
        if is_coordinator(a):
            return {"ok": False,
                    "error": ("The coordinator's access follows the role, not a grant list — "
                              "switch the capability off for the realm, or make this agent "
                              "not the coordinator.")}
        tk = a.get("toolkit") or {}
        removed = False
        for k in KINDS:
            before = list(tk.get(k) or [])
            after = [c for c in before if cap_key(c) != want]
            if len(after) != len(before):
                tk[k] = after
                removed = True
        if removed:
            a["toolkit"] = tk
            util.write_json_atomic(ap, a)
    return {"ok": True, "removed": removed}


def grant_record(realm_root, agent, cap_id) -> dict:
    """The agent's own grant entry for a capability — carries granted_at / granted_via / thread."""
    want = cap_key(cap_id)
    g = grants(realm_root, agent)
    for k in KINDS:
        for c in g[k]:
            if cap_key(c) == want:
                return c
    return {}


def granted_in_thread(realm_root, agent, cap_id, thread: str) -> bool:
    """Was this capability granted to this agent through THIS conversation?

    What the thread panel needs to tell "the agent just gained this" apart from "the agent already
    had it and used it here" — two very different things for someone deciding whether to worry.
    """
    if not thread:
        return False
    rec = grant_record(realm_root, agent, cap_id)
    return bool(rec) and str(rec.get("granted_thread") or "") == str(thread)


# --------------------------------------------------------------------------- enforcement

class CapabilityPolicyError(ValueError):
    """A tool turn cannot safely determine its permissions."""


@dataclass(frozen=True)
class CapabilityPolicy:
    """Validated per-turn MCP grants. An empty set grants no MCP servers."""
    allowed_mcp_ids: frozenset[str]
    denied_tools: tuple[str, ...]
    # Recognized local filesystem extensions can use a provider's scoped native
    # file tools. Identity comes from the catalogue, never from a server-name guess.
    native_filesystem_ids: frozenset[str] = frozenset()


def _policy_json(path: Path) -> dict:
    try:
        return util.read_json_state(path)
    except util.UnsupportedSchemaError:
        raise
    except (OSError, ValueError, UnicodeError) as exc:
        # Do not include policy contents or decoder excerpts in an error/run report.
        raise CapabilityPolicyError(f"Capability policy: cannot read valid {path.name}; repair the file before running tools.") from exc


def _policy_toolkit(data: dict, label: str, *, grants_only=False) -> dict:
    tk = data.get("toolkit", {})
    if not isinstance(tk, dict):
        raise CapabilityPolicyError(f"Capability policy: {label}.toolkit must be an object.")
    result = {}
    for kind in KINDS:
        entries = tk.get(kind, [])
        if not isinstance(entries, list):
            raise CapabilityPolicyError(f"Capability policy: {label}.toolkit.{kind} must be a list.")
        result[kind] = []
        seen = set()
        for item in entries:
            if isinstance(item, str) and grants_only:
                item = {"id": item}
            if not isinstance(item, dict):
                raise CapabilityPolicyError(f"Capability policy: invalid entry in {label}.toolkit.{kind}.")
            for field in ("id", "name"):
                value = item.get(field, "")
                if not isinstance(value, str) or any(ord(c) < 32 for c in value):
                    raise CapabilityPolicyError(f"Capability policy: invalid {field} in {label}.toolkit.{kind}.")
            if "enabled" in item and type(item["enabled"]) is not bool:
                raise CapabilityPolicyError(f"Capability policy: enabled must be true or false in {label}.")
            key = cap_key(item)
            if not key or key in seen:
                raise CapabilityPolicyError(f"Capability policy: missing or duplicate identity in {label}.toolkit.{kind}.")
            sid = item.get("id", "")
            if kind in MCP_KINDS and sid and (sid != sid.strip() or any(c in sid for c in "*?()[]{}\\\"")):
                raise CapabilityPolicyError(f"Capability policy: invalid MCP server identity in {label}.")
            seen.add(key)
            result[kind].append(item)
    return result


def execution_policy(realm_root, agent) -> CapabilityPolicy:
    """Read policy strictly for execution; display/discovery fallbacks never authorize tools."""
    realm = _policy_json(Path(realm_root) / "realm.json")
    a = agent if isinstance(agent, dict) else _policy_json(
        Path(realm_root) / "agents" / util.safe_seg(str(agent), "agent") / "agent.json")
    if "coordinator" in a and type(a["coordinator"]) is not bool:
        raise CapabilityPolicyError("Capability policy: coordinator must be true or false.")
    cat = _policy_toolkit(realm, "realm")
    from .connector_runtime import is_provider_placeholder
    cat["connectors"] = [c for c in cat["connectors"] if not is_provider_placeholder(c)]
    granted = _policy_toolkit(a, "agent", grants_only=True)
    allowed, denied = set(), set()
    for kind in MCP_KINDS:
        keys = {cap_key(c) for c in granted[kind] if realm_enabled(c)}
        for cap in cat[kind]:
            sid = cap.get("id", "")
            if not sid:
                continue  # Descriptive entries cannot grant an MCP identity.
            if realm_enabled(cap) and (a.get("coordinator", False) or cap_key(cap) in keys):
                allowed.add(sid)
            else:
                denied.add(sid)
    # A disabled or ungranted duplicate in another kind always wins.
    allowed.difference_update(denied)
    native_filesystem = frozenset(
        c["id"] for c in cat["extensions"]
        if c.get("id") and c.get("extension_id") == "ant.dir.ant.anthropic.filesystem")
    return CapabilityPolicy(frozenset(allowed), tuple(f"mcp__{sid}" for sid in sorted(denied)),
                            native_filesystem)

def denied_tool_patterns(realm_root, agent) -> list:
    """Compatibility facade for validated catalogue denials; adapters also gate their inventory."""
    return list(execution_policy(realm_root, agent).denied_tools)


def provider_policy(policy: CapabilityPolicy, provider: str) -> CapabilityPolicy:
    """Resolve approved logical identities to the provider's actual registration names."""
    if provider not in ("claude", "codex", "gemini"):
        return policy
    from .engine.mcp import registration_id
    blocked = {registration_id(t.removeprefix("mcp__")) for t in policy.denied_tools}
    if provider == "claude":
        # Preserve the cloud/display registration and also admit the safe direct
        # name shown by Set up. A disabled alias always revokes both identities.
        allowed = {sid for sid in policy.allowed_mcp_ids if registration_id(sid) not in blocked}
        allowed |= {registration_id(sid) for sid in allowed}
        return CapabilityPolicy(frozenset(allowed), policy.denied_tools, policy.native_filesystem_ids)
    allowed = {registration_id(sid) for sid in policy.allowed_mcp_ids} - blocked
    return CapabilityPolicy(frozenset(allowed), tuple("mcp__" + sid for sid in sorted(blocked)),
                            frozenset(registration_id(sid) for sid in policy.native_filesystem_ids))


# --------------------------------------------------------------------------- requests

_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(s: str) -> str:
    return _SLUG.sub("-", str(s or "").strip().lower()).strip("-")[:60] or "capability"


def requests_dir(realm_root, agent_id: str) -> Path:
    return Path(realm_root) / "agents" / util.safe_seg(agent_id, "agent") / REQUESTS_DIR


def request(realm_root, agent_id: str, cap_id: str, reason: str = "", thread: str = "") -> dict:
    """Record an agent asking to use a realm capability. Nothing is granted by this."""
    kind, cap = find(realm_root, cap_id)
    if not kind:
        return {"ok": False, "error": f"No capability '{cap_id}' in this realm."}
    if may_use(realm_root, agent_id, cap_id):
        return {"ok": True, "already": True}
    d = requests_dir(realm_root, agent_id)
    d.mkdir(parents=True, exist_ok=True)
    slug = _slug(cap.get("id") or cap.get("name"))
    util.write_json_atomic(d / f"{slug}.json", {
        "capability": cap.get("id") or cap.get("name"), "kind": kind,
        "name": cap.get("name") or cap.get("id"), "reason": str(reason or "")[:600],
        "thread": thread, "asked_at": _now(),
    })
    return {"ok": True, "slug": slug}


def iter_requests(realm_root):
    """(agent_id, slug, request, path) for every outstanding capability request."""
    adir = Path(realm_root) / "agents"
    for ap in sorted(p for p in adir.iterdir() if p.is_dir()) if adir.is_dir() else []:
        d = ap / REQUESTS_DIR
        for f in sorted(d.glob("*.json")) if d.is_dir() else []:
            r = _read(f)
            if r:
                yield ap.name, f.stem, r, f


def count_requests(realm_root) -> int:
    return sum(1 for _ in iter_requests(realm_root))


def approve_request(realm_root, agent_id: str, slug: str) -> dict:
    """Grant what was asked for, recording the thread it was asked in."""
    f = requests_dir(realm_root, agent_id) / f"{util.safe_seg(slug, 'req')}.json"
    r = _read(f)
    if not r:
        return {"ok": False, "error": "request not found"}
    res = grant(realm_root, agent_id, r.get("capability"), via="thread",
                thread=str(r.get("thread") or ""))
    if res.get("ok"):
        try:
            f.unlink()
        except OSError:
            pass
    return res


def reject_request(realm_root, agent_id: str, slug: str) -> dict:
    f = requests_dir(realm_root, agent_id) / f"{util.safe_seg(slug, 'req')}.json"
    try:
        if f.exists():
            f.unlink()
    except OSError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True}
