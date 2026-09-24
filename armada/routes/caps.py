"""Capabilities/skills.

save/delete/toggle/permission, scan-updates, version update, skill content, connectors
refresh, grant/revoke/request approve-reject, open/reveal/delete an artefact.

Split out of serve.py (Phase 2, 2.3) — a pure move, no behaviour change; the route table
stays in serve.py, only the handler bodies moved.
"""
from __future__ import annotations
import http.server, io, json, logging, os, subprocess, sys, threading, time, urllib.parse, contextlib
from pathlib import Path
from .. import activerealm, reader, render, scheduler, util, brand
from ..util import safe_seg
from . import _shared
from ..util import swallowed

log = logging.getLogger("armada.serve")


class CapabilityRoutes:
    def _read_claude_mcp(self) -> list:
        """Best-effort: enumerate MCP servers Claude Code can see (~/.claude.json + project scopes + .mcp.json)."""
        names = set()
        candidates = [Path.home() / ".claude.json"]
        for cfg in candidates:
            if not cfg.exists():
                continue
            try:
                data = json.loads(cfg.read_text(encoding="utf-8-sig"))
            except Exception:  # noqa
                swallowed(log, '_read_claude_mcp: failed; skipping this one')
                continue
            for k in (data.get("mcpServers") or {}):
                names.add(k)
            for proj in (data.get("projects") or {}).values():
                for k in (proj.get("mcpServers") or {}):
                    names.add(k)
        # project-local .mcp.json next to the realm
        for mcp in (Path(self.realm) / ".mcp.json", Path(self.realm).parent / ".mcp.json"):
            if mcp.exists():
                try:
                    for k in (json.loads(mcp.read_text(encoding="utf-8-sig")).get("mcpServers") or {}):
                        names.add(k)
                except Exception:  # noqa
                    swallowed(log, '_read_claude_mcp: failed; ignored')
        return sorted(names)

    def _refresh_connectors(self, body: dict) -> dict:
        """Pull the MCP servers the CLI knows about into this scope's catalogue.

        Delegates to capscan.reconcile, which is the one place that knows the classification rule:
        a server whose config entry is a URL runs somewhere else (Connector), one whose entry is a
        command runs here (Extension). This handler used to file every server as a Connector and
        de-duplicate against the connectors list alone — so a refresh added a second, mislabelled
        copy of every local server already listed as an Extension, and each copy claimed to be a
        remote service. The realm catalogue is what agents are granted from; two entries for one
        server means granting the wrong one silently grants nothing.
        """
        from .. import capscan
        scope = str(body.get("scope", "realm"))
        p = self._cap_target(scope)
        if not p.exists():
            return {"ok": False, "error": f"no {scope}"}
        # Locked read-modify-write: this is the same realm.json (or agent.json) the scheduler
        # daemon's own capability scan (capscan.scan) writes, unlocked before this pass — two
        # writers racing here is exactly the "two edits of realm.json" case file_lock exists for.
        with util.file_lock(p):
            try:
                js = json.loads(p.read_text(encoding="utf-8-sig"))
            except Exception as e:  # noqa
                swallowed(log, '_refresh_connectors: failed; error returned to the caller')
                return {"ok": False, "error": str(e)}
            tk = js.setdefault("toolkit", {})
            before = sum(len(tk.get(k) or []) for k in ("connectors", "extensions", "skills", "plugins"))
            mcp = capscan.list_mcp()
            # discover=True on purpose, and only here. Discovery is off by default now — a version
            # scan must not file things into a realm nobody added them to — but this handler exists
            # because someone pressed a button that says "pull them in", in the realm they are
            # standing in. That is the invitation.
            changed = capscan.reconcile(tk, [], mcp, discover=True)   # [] = plugins; this is servers
            # Clean up after the version of this handler that made duplicates. Doing it on refresh
            # means a realm already damaged repairs itself the next time someone presses the
            # button, rather than needing a migration nobody would know to run.
            dropped = self._dedupe_toolkit(tk)
            added = sum(len(tk.get(k) or []) for k in ("connectors", "extensions", "skills", "plugins")) - before
            if changed or dropped:
                util.write_json_atomic(p, js)
        return {"ok": True, "found": len(mcp), "added": max(added, 0), "removed": len(dropped),
                "dropped": dropped[:20]}

    @staticmethod
    def _dedupe_toolkit(tk: dict) -> list:
        """Drop entries that name a capability already listed under another kind. Returns what went.

        Repairs realms that a previous refresh duplicated. The keeper is the entry with the richer
        record — a discovered one carries `runs` and `touch`, the mislabelled copies did not — and
        on a tie the earlier kind wins so the order of KINDS decides rather than dict iteration.
        """
        from .. import capabilities as caps
        seen, dropped = {}, []
        for kind in caps.KINDS:
            keep = []
            for it in (tk.get(kind) or []):
                k = caps.cap_key(it)
                if not k:
                    keep.append(it)
                    continue
                prev = seen.get(k)
                if prev is None:
                    seen[k] = (kind, it)
                    keep.append(it)
                    continue
                # Already have one. Keep whichever says more about what it actually is.
                score = lambda c: (1 if c.get("runs") else 0) + (1 if c.get("touch") else 0)
                if score(it) > score(prev[1]):
                    pk, pit = prev
                    tk[pk] = [c for c in (tk.get(pk) or []) if c is not pit]
                    dropped.append({"kind": pk, "id": pit.get("id") or pit.get("name")})
                    seen[k] = (kind, it)
                    keep.append(it)
                else:
                    dropped.append({"kind": kind, "id": it.get("id") or it.get("name")})
            tk[kind] = keep
        return dropped

    def _cap_target(self, scope: str):
        """Return (json_path) for a capability scope: 'realm' -> realm.json, else agent.json."""
        if scope == "realm":
            return Path(self.realm) / "realm.json"
        return Path(self.realm) / "agents" / safe_seg(scope, "agent") / "agent.json"

    def _save_capability(self, body: dict) -> dict:
        import re
        scope = str(body.get("scope", ""))
        kind = str(body.get("kind", ""))
        if kind not in ("connectors", "extensions", "skills", "plugins"):
            return {"ok": False, "error": "bad kind"}
        name = str(body.get("name", "")).strip()
        if not name:
            return {"ok": False, "error": "name required"}
        p = self._cap_target(scope)
        if not p.exists():
            return {"ok": False, "error": f"no {scope}"}
        with util.file_lock(p):
            try:
                js = json.loads(p.read_text(encoding="utf-8-sig"))
            except Exception as e:  # noqa
                swallowed(log, '_save_capability: failed; error returned to the caller')
                return {"ok": False, "error": str(e)}
            tk = js.setdefault("toolkit", {})
            lst = tk.setdefault(kind, [])
            icon = {"connectors": "cap-connector", "extensions": "puzzle",
                    "skills": "cap-skill", "plugins": "cap-plugin"}[kind]
            cid = str(body.get("id", "")).strip()
            item = {"name": name, "description": str(body.get("descr", "")).strip(),
                    "status": (str(body.get("status", "connected")).lower() or "connected"),
                    "source": "custom", "icon": icon}
            if cid:  # edit existing (custom only)
                found = False
                for it in lst:
                    if it.get("id") == cid:
                        if (it.get("source") or "3p") != "custom":
                            return {"ok": False, "error": "third-party items can't be edited"}
                        it.update({"name": item["name"], "description": item["description"], "status": item["status"]})
                        found = True
                        break
                if not found:
                    return {"ok": False, "error": "not found"}
            else:  # add new
                base = re.sub(r"[^a-z0-9\-]", "", name.lower().replace(" ", "-"))[:40] or "custom"
                new_id = base
                existing = {it.get("id") for it in lst}
                n = 2
                while new_id in existing:
                    new_id = f"{base}-{n}"; n += 1
                item["id"] = new_id
                lst.append(item)
            util.write_json_atomic(p, js)
        return {"ok": True}

    def _toggle_capability(self, body: dict) -> dict:
        scope = str(body.get("scope", ""))
        kind = str(body.get("kind", ""))
        cid = str(body.get("id", ""))
        p = self._cap_target(scope)
        if not p.exists():
            return {"ok": False, "error": f"no {scope}"}
        with util.file_lock(p):
            try:
                js = json.loads(p.read_text(encoding="utf-8-sig"))
            except Exception as e:  # noqa
                swallowed(log, '_toggle_capability: failed; error returned to the caller')
                return {"ok": False, "error": str(e)}
            lst = (js.get("toolkit", {}) or {}).get(kind, []) or []
            for it in lst:
                if it.get("id") == cid:
                    it["enabled"] = bool(body.get("enabled", True))
                    util.write_json_atomic(p, js)
                    return {"ok": True}
        return {"ok": False, "error": "not found"}

    def _set_cap_permission(self, body: dict) -> dict:
        scope = str(body.get("scope", "")); kind = str(body.get("kind", "")); cid = str(body.get("id", ""))
        perm = str(body.get("permission", "allow")).lower()
        if perm not in ("allow", "ask"):
            perm = "allow"
        p = self._cap_target(scope)
        if not p.exists():
            return {"ok": False, "error": f"no {scope}"}
        with util.file_lock(p):
            try:
                js = json.loads(p.read_text(encoding="utf-8-sig"))
            except Exception as e:  # noqa
                swallowed(log, '_set_cap_permission: failed; error returned to the caller')
                return {"ok": False, "error": str(e)}
            for it in (js.get("toolkit", {}) or {}).get(kind, []) or []:
                if it.get("id") == cid:
                    if perm == "allow":
                        it.pop("permission", None)
                    else:
                        it["permission"] = perm
                    util.write_json_atomic(p, js)
                    return {"ok": True}
        return {"ok": False, "error": "not found"}

    def _scan_updates(self, body: dict) -> dict:
        """Scan CLI-known capabilities for real installed/latest versions (read-only)."""
        from .. import capscan, notify as _n
        r = capscan.scan(self.realm)
        # Worth telling the owner about, not worth interrupting them for — so this lands in the
        # in-app feed only, never as a desktop notification.
        n = int(r.get("updates") or 0)
        if r.get("ok") and n:
            _n.emit(self.realm, "update_available",
                    f"{n} capability update{'s' if n != 1 else ''} available",
                    "Review and apply them on the Capabilities page.", "/skills")
        return r

    def _update_capability_version(self, body: dict) -> dict:
        """Apply an available update. Plugins are updated for real via `claude plugin update`; other
        types are managed by the Claude app, not the CLI, so ARMADA can't fetch/install them here."""
        scope = str(body.get("scope", "")); kind = str(body.get("kind", "")); cid = str(body.get("id", ""))
        p = self._cap_target(scope)
        if not p.exists():
            return {"ok": False, "error": f"no {scope}"}
        try:
            js = json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception as e:  # noqa
            swallowed(log, '_update_capability_version: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}
        item = next((it for it in (js.get("toolkit", {}) or {}).get(kind, []) or [] if it.get("id") == cid), None)
        if item is None:
            return {"ok": False, "error": "not found"}
        if str(item.get("latest") or "").strip() in ("", str(item.get("version") or "").strip()):
            return {"ok": False, "error": "no update available"}
        if kind != "plugins":
            return {"ok": False, "error": "This is managed by the Claude app, not the CLI — "
                    "ARMADA can't update it automatically. Update it in Claude."}
        from .. import capscan
        res = capscan.apply_plugin_update(str(item.get("id") or ""))
        if not res.get("ok"):
            return {"ok": False, "error": ("update failed: " + (res.get("out") or "not CLI-managed"))[:220]}
        capscan.scan(self.realm)   # refresh real installed/latest after the update
        return {"ok": True}

    def _skill_md_path(self, sid: str):
        """Best-effort locate a skill's SKILL.md across the realm and the usual skill roots."""
        sid = safe_seg(sid, "skill")
        realm = Path(self.realm)
        cands = [realm / "skills" / sid / "SKILL.md"]
        adir = realm / "agents"
        if adir.is_dir():
            for ad in adir.iterdir():
                cands.append(ad / "skills" / sid / "SKILL.md")
        home = Path(os.path.expanduser("~"))
        cands += [home / ".claude" / "skills" / sid / "SKILL.md",
                  home / ".agents" / "skills" / sid / "SKILL.md"]
        for c in cands:
            try:
                if c.is_file():
                    return c
            except Exception:  # noqa
                log.debug('_skill_md_path: failed; skipping this one', exc_info=True)
                continue
        return None

    def _get_skill_content(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        sid = (q.get("id") or [""])[0]
        if (q.get("scope") or [""])[0] == "system":
            # System skills live inside the package, not the realm — resolve them through the
            # registry (which does its own id validation) rather than the realm search path.
            from .. import sysskills
            it = sysskills.get_system_skill(sid)
            if not it:
                self._json(200, {"ok": False, "error": "Unknown system skill."})
                return
            from ..webui._base import _md
            self._json(200, {"ok": True, "name": it["name"], "html": _md(it["body"])})
            return
        path = self._skill_md_path(sid)
        if not path:
            self._json(200, {"ok": False, "error": "The source for this skill isn't available on this machine."})
            return
        try:
            import re
            from ..webui._base import _md
            txt = path.read_text(encoding="utf-8-sig")
            m = re.match(r"^---\r?\n.*?\r?\n---\r?\n", txt, re.S)   # drop leading YAML frontmatter for display
            body = txt[m.end():] if m else txt
            self._json(200, {"ok": True, "name": sid, "html": _md(body)})
        except Exception as e:  # noqa
            swallowed(log, '_get_skill_content: failed; reported to the caller')
            self._json(200, {"ok": False, "error": str(e)})

    # Opening a file hands it to whatever program Windows has associated with the extension. For a
    # .docx or .pdf that's exactly what the owner wants; for a .bat or .exe it is a double-click that
    # RUNS it. Agents write these files, so the list is not a trusted source of things to execute —
    # anything runnable is revealed in the file manager instead, where opening it stays a deliberate
    # human act. (Reveal is always safe: it only selects the file.)
    _RUNNABLE = {
        ".exe", ".com", ".scr", ".pif", ".msi", ".msp", ".cpl", ".jar", ".lnk", ".inf",
        ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe", ".wsf", ".wsh", ".hta", ".reg",
        ".js", ".jse", ".py", ".pyw", ".rb", ".pl", ".sh",
    }

    def _artefact_roots(self) -> list:
        """Where an artefact the app may open or delete can live: this realm, its workspace root, and
        the app root every realm sits in. Nothing outside them (THREAT_MODEL T6)."""
        from .. import approot, workspace
        roots = [Path(self.realm)]
        for r in (workspace.root(self.realm), approot.root()):
            if r:
                roots.append(Path(r))
        out = []
        for r in roots:
            try:
                out.append(r.resolve())
            except OSError:
                log.debug("_artefact_roots: unresolvable root %s", r, exc_info=True)
        return out

    def _within_artefact_roots(self, p: Path) -> bool:
        return any(p == r or p.is_relative_to(r) for r in self._artefact_roots())

    _OUTSIDE = ("That file is outside this realm, its workspace and the ARMADA folder — "
                "ARMADA only opens or deletes files there.")

    def _open_file(self, body: dict) -> dict:
        """Open an artifact with its default application (local, single-user app)."""
        raw = str(body.get("path", "")).strip()
        if not raw:
            return {"ok": False, "error": "no path"}
        try:
            p = Path(raw).resolve()
        except Exception as e:  # noqa
            log.debug('_open_file: failed; error returned to the caller', exc_info=True)
            return {"ok": False, "error": f"bad path: {e}"}
        if not p.is_file():
            return {"ok": False, "error": "file not found on disk"}
        if not self._within_artefact_roots(p):
            return {"ok": False, "error": self._OUTSIDE}
        if p.suffix.lower() in self._RUNNABLE:
            r = self._reveal({"path": str(p)})
            r["revealed"] = True
            r["error"] = (f"{p.suffix} files can run code, so ARMADA showed it in the folder "
                          f"instead of opening it.")
            return r
        try:
            if os.name == "nt":
                os.startfile(str(p))  # noqa: S606 — the documented way to open with the default app
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
            return {"ok": True}
        except Exception as e:  # noqa
            swallowed(log, '_open_file: failed; error returned to the caller')
            return {"ok": False, "error": str(e)[:200]}

    def _delete_artefact(self, body: dict) -> dict:
        """Delete an artifact file from disk. The thread's record of it is left alone — history
        shouldn't silently rewrite itself; the row simply stops offering actions."""
        raw = str(body.get("path", "")).strip()
        if not raw:
            return {"ok": False, "error": "no path"}
        try:
            p = Path(raw).resolve()
        except Exception as e:  # noqa
            log.debug('_delete_artefact: failed; error returned to the caller', exc_info=True)
            return {"ok": False, "error": f"bad path: {e}"}
        if not p.is_file():
            return {"ok": False, "error": "file not found on disk"}
        if not self._within_artefact_roots(p):
            return {"ok": False, "error": self._OUTSIDE}
        try:
            p.unlink()
            return {"ok": True}
        except Exception as e:  # noqa
            swallowed(log, '_delete_artefact: failed; error returned to the caller')
            return {"ok": False, "error": str(e)[:200]}

    def _cap_grant(self, body: dict) -> dict:
        """Map a realm capability to an agent — the owner doing it deliberately, from the
        Capabilities page. Recorded as via='user' so the thread rail won't call it new."""
        from .. import capabilities as caps
        return caps.grant(self.realm, str(body.get("agent") or ""),
                          str(body.get("capability") or ""), via="user")

    def _cap_revoke(self, body: dict) -> dict:
        from .. import capabilities as caps
        return caps.revoke(self.realm, str(body.get("agent") or ""),
                           str(body.get("capability") or ""))

    def _cap_request_approve(self, body: dict) -> dict:
        """Approve what an agent asked for in a thread. The grant remembers that thread, which is
        what makes it show as new there."""
        from .. import capabilities as caps
        return caps.approve_request(self.realm, str(body.get("agent") or ""),
                                    str(body.get("slug") or ""))

    def _cap_request_reject(self, body: dict) -> dict:
        from .. import capabilities as caps
        return caps.reject_request(self.realm, str(body.get("agent") or ""),
                                   str(body.get("slug") or ""))

    def _reveal_skill(self, body: dict) -> dict:
        """Open the OS file manager with a skill's SKILL.md selected.

        The path is never taken from the request — only a skill id, resolved through the same
        trusted lookups the viewer uses (the bundled registry, or the realm/home skill roots). So
        this can only ever reveal a file ARMADA already knows about, not an arbitrary path.
        """
        sid = str(body.get("id", ""))
        if str(body.get("scope", "")) == "system":
            from .. import sysskills
            it = sysskills.get_system_skill(sid)
            path = Path(it["path"]) if it else None
        else:
            path = self._skill_md_path(sid)
        if not path or not Path(path).is_file():
            return {"ok": False, "error": "The file for this skill isn't available on this machine."}
        return self._reveal({"path": str(Path(path).resolve())})   # one place does the OS call

    def _delete_capability(self, body: dict) -> dict:
        scope = str(body.get("scope", ""))
        kind = str(body.get("kind", ""))
        cid = str(body.get("id", ""))
        p = self._cap_target(scope)
        if not p.exists():
            return {"ok": False, "error": f"no {scope}"}
        with util.file_lock(p):
            try:
                js = json.loads(p.read_text(encoding="utf-8-sig"))
            except Exception as e:  # noqa
                swallowed(log, '_delete_capability: failed; error returned to the caller')
                return {"ok": False, "error": str(e)}
            lst = (js.get("toolkit", {}) or {}).get(kind, []) or []
            new = [it for it in lst if it.get("id") != cid]
            if len(new) == len(lst):
                return {"ok": False, "error": "not found"}
            js["toolkit"][kind] = new
            util.write_json_atomic(p, js)
        return {"ok": True}

    def _reveal(self, body: dict) -> dict:
        """Open the OS file explorer at an OUTPUT artifact (selecting the file). ARMADA is a local,
        single-user app, so revealing a path the agent itself wrote on this machine is safe; we still
        require the path to exist and be a real file before handing it to the shell."""
        raw = str(body.get("path", "")).strip()
        if not raw:
            return {"ok": False, "error": "no path"}
        try:
            p = Path(raw).resolve()
        except Exception as e:  # noqa
            log.debug('_reveal: failed; error returned to the caller', exc_info=True)
            return {"ok": False, "error": f"bad path: {e}"}
        if not p.is_file():
            return {"ok": False, "error": "file not found on disk"}
        try:
            if os.name == "nt":
                # explorer /select, "<path>" highlights the file in its folder. explorer returns a
                # non-zero exit even on success, so we don't check returncode.
                subprocess.Popen(["explorer", "/select,", str(p)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p.parent)])
        except Exception as e:  # noqa
            log.exception("reveal failed for %s", p)
            return {"ok": False, "error": f"could not open: {e}"}
        return {"ok": True}

