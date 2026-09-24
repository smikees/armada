"""Realm lifecycle: switch/new/archive/export/delete, preflight, workspace/approot, icon,
settings, covenant.

Split out of serve.py (Phase 2, 2.3) — a pure move, no behaviour change; the route table
stays in serve.py, only the handler bodies moved.
"""
from __future__ import annotations
import http.server, io, json, logging, os, subprocess, sys, threading, time, urllib.parse, contextlib
from pathlib import Path
from .. import activerealm, reader, realmformat, render, scheduler, util, brand
from ..util import safe_seg
from . import _shared
from ._shared import _reg_load, _reg_save, _reg_rename, _reg_ensure, _realm_json
from ..util import swallowed

log = logging.getLogger("armada.serve")


class RealmRoutes:
    def _get_index(self):
        from .. import webui
        try:
            self._send(200, webui.render_dashboard(reader.read(self.realm), self.realm, dark=self._dark()))
        except SystemExit as e:
            self._err_page(e)

    def _get_realm_page(self, page):
        from .. import webui
        try:
            self._send(200, webui.render_realm_page(reader.read(self.realm), self.realm, page,
                                                    dark=self._dark()))
        except SystemExit as e:
            self._err_page(e)

    def _get_new_realm(self):
        from .. import webui
        q = self._query()
        self._send(200, webui.render_new_realm(reader.read(self.realm), dark="dark" in q, embed="embed" in q))

    def _get_switch(self):
        q = self._query()
        newp = q.get("path", "")
        if newp and activerealm.is_realm(newp):
            realmformat.ensure(newp)          # opening a realm brings its format up to date (2.8)
            first = not type(self).realm      # leaving the first-run page (5.3)
            type(self).realm = newp
            type(self).welcome_note = ""
            if first:
                # The window's launch-time scheduler start had no realm to start for; now there is
                # one. A running scheduler picks the new realm up by itself (5.5 rescan).
                from .. import schedsvc
                threading.Thread(target=schedsvc.ensure_running, args=(newp,), daemon=True).start()
            # Remember it on the machine, not just in this process: closing the app and reopening
            # it from a shortcut has to land in the realm you switched to, the same way Update &
            # Restart does. Without this the two ways of restarting disagree.
            activerealm.remember(newp)
        to = q.get("to", "/")
        if not to.startswith("/") or to.startswith("//"):  # only local paths
            to = "/"
        self.send_response(302); self.send_header("Location", to); self.end_headers()

    def _get_pick_folder(self):
        self._json(200, self._pick_folder())

    def _get_check_update(self):
        self._json(200, self._git_check())

    def _get_realms(self):
        cur = str(Path(self.realm).resolve())
        realms = _reg_load()
        name = next((r["name"] for r in realms if r["path"] == cur), Path(self.realm).name)
        self._json(200, {"current": cur, "current_name": name, "realms": realms})

    def _get_realm_icon(self):
        f = None
        for ext in ("png", "jpg", "jpeg", "webp", "svg"):
            cand = Path(self.realm) / f"icon.{ext}"
            if cand.is_file():
                f = cand; break
        if f:
            ct = "image/svg+xml" if f.suffix == ".svg" else self._CT.get(f.suffix.lower(), "image/png")
            self._send(200, f.read_bytes(), ct)
        else:
            self._send(404, "no icon", "text/plain")

    def _get_realm(self):
        try:
            self._json(200, _realm_json(reader.read(self.realm)))
        except SystemExit as e:
            self._json(400, {"error": str(e)})

    def _pick_folder(self) -> dict:
        """Open a native folder picker on the user's machine (local app).

        The app window's own dialog first: the real Windows picker, parented to the window (so it
        can't open behind it), and the only option in the installed build — the embeddable Python
        it ships has no tkinter (ADR-009). tkinter stays as the fallback for `armada serve` in a
        browser, where this process has no window."""
        try:
            import webview
            wins = list(getattr(webview, "windows", []) or [])
            if wins:
                kind = getattr(getattr(webview, "FileDialog", None), "FOLDER", None)
                if kind is None:
                    kind = webview.FOLDER_DIALOG
                picked = wins[0].create_file_dialog(kind)
                path = (picked[0] if isinstance(picked, (list, tuple)) and picked else picked) or ""
                return {"ok": bool(path), "path": str(path)}
        except ImportError:
            pass
        except Exception:  # noqa — fall through to tkinter
            swallowed(log, "_pick_folder: window dialog failed; trying tkinter")
        try:
            import tkinter
            from tkinter import filedialog
            r = tkinter.Tk(); r.withdraw(); r.attributes("-topmost", True)
            path = filedialog.askdirectory(title="Choose a folder for the realm")
            r.destroy()
            return {"ok": bool(path), "path": path or ""}
        except Exception as e:  # noqa
            swallowed(log, '_pick_folder: failed; error returned to the caller')
            return {"ok": False, "error": f"picker unavailable ({e}) — type the path"}

    def _new_realm(self, body: dict) -> dict:
        mode, name, path = body.get("mode", "create"), (body.get("name") or "").strip(), (body.get("path") or "").strip()
        if not path:
            return {"ok": False, "error": "folder required"}
        p = Path(path)
        # Every realm lives inside the app root. Refusing here is the one place the rule can be
        # enforced cheaply and completely: once a realm exists outside the root, everything
        # downstream — backups, containment, "what can this install touch" — is already wrong.
        from .. import approot
        gate = approot.check(p)
        if not gate["ok"]:
            out = {"ok": False, "error": gate["error"], "code": gate["code"]}
            if gate["code"] == "outside-root":
                out["suggested_path"] = approot.suggest_for(p)
            return out
        try:
            if mode == "adopt":
                if not ((p / "realm.json").exists() or (p / "cabinet" / "schedule.json").exists()):
                    return {"ok": False, "error": "no realm.json or cabinet/ in that folder"}
            else:
                from ..setup import scaffold
                scaffold(str(p), body.get("template", "scratch"), name or p.name,
                         icon=body.get("icon") or None, agents=body.get("agents"))
            if body.get("iconData"):
                self._write_data_image(p / "icon", body["iconData"])
            # Import: an adopted folder may come from an older ARMADA (2.8). A newer one is
            # reported rather than refused — it still opens, with the tolerant readers.
            fmt = realmformat.migrate(p)
            # An adopted realm is someone else's jobs; they wait for the owner's go-ahead (5.8c).
            from .. import preflight as _pf
            review = _pf.begin_adopt_review(p) if mode == "adopt" else {}
            _reg_ensure(str(p), name or p.name)
            out = {"ok": True, "path": str(p.resolve())}
            if review.get("command_jobs") or review.get("agent_jobs"):
                out["review"] = review
            if fmt.get("newer"):
                out["format_warning"] = (f"This realm was saved by a newer version of ARMADA (format "
                                         f"v{fmt['from']}; this one understands v{realmformat.CURRENT}). "
                                         "It will open, but update ARMADA before editing it.")
            # Adopting an existing folder is how a realm arrives from another machine, and the parts
            # that don't travel — the workspace root, the engine sign-in — are invisible until a job
            # fails at 03:00. Check on arrival, while someone is looking, and hold the scheduler if
            # it can't work. A freshly scaffolded realm is checked too; it just has nothing to fail.
            try:
                from .. import preflight, workspace as ws
                pf = preflight.apply_hold(p)
                if any(c["id"] == "workspace" and not c["ok"] for c in pf["checks"]):
                    pf["suggested_root"] = ws.detect_root(p)
                out["preflight"] = pf
            except Exception as e:  # noqa — a failed check must not block adding the realm
                swallowed(log, '_new_realm: failed; recorded as an error')
                out["preflight_error"] = str(e)[:200]
            return out
        except SystemExit as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:  # noqa
            swallowed(log, '_new_realm: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _save_realm_settings(self, body: dict) -> dict:
        rj = Path(self.realm) / "realm.json"
        if not rj.exists():
            return {"ok": False, "error": "no realm.json"}
        try:
            with util.file_lock(rj):
                cfg = json.loads(rj.read_text(encoding="utf-8-sig"))
                if isinstance(body.get("providers"), list):
                    # Keep at least one engine selected — a realm with none can't run anything,
                    # and that's a broken state rather than a preference.
                    provs = [str(p) for p in body["providers"] if str(p).strip()]
                    if provs:
                        cfg["providers"] = provs
                # The realm's name is a label, not an identity: the folder is what jobs, memories
                # and run reports are keyed on, so renaming breaks nothing. Blank falls back to
                # the folder name rather than storing an empty string, because a realm with no
                # name at all renders as a gap in the switcher.
                if "name" in body:
                    nm = str(body.get("name") or "").strip()[:60]
                    cfg["name"] = nm or Path(self.realm).name
                    # The switcher and the menu read the registry, not realm.json. Renaming in one
                    # place and not the other is how the same realm comes to have two names on one
                    # screen.
                    _reg_rename(self.realm, cfg["name"])
                if "default_verbosity" in body:
                    from .. import verbosity as _verbosity
                    v = _verbosity.normalise(body.get("default_verbosity"))
                    if v:
                        cfg["default_verbosity"] = v
                    else:
                        cfg.pop("default_verbosity", None)
                if "timezone" in body:       # moved here from User settings — it's a realm fact
                    cfg["timezone"] = (body.get("timezone") or "").strip()
                    if not cfg["timezone"]:
                        cfg.pop("timezone", None)      # blank = follow the OS timezone
                for k in ("provider", "default_model", "default_effort", "default_fallback_model"):
                    if body.get(k):
                        cfg[k] = body[k]
                    elif k == "default_fallback_model" and "default_fallback_model" in body:
                        cfg.pop(k, None)              # blank fallback = clear the realm default
                if "default_max_budget_usd" in body:     # Advanced: realm-wide per-run spend cap
                    try:
                        b = float(body["default_max_budget_usd"])
                    except (TypeError, ValueError):
                        b = 0.0
                    if b > 0:
                        cfg["default_max_budget_usd"] = b
                    else:
                        cfg.pop("default_max_budget_usd", None)
                if isinstance(body.get("inbox"), dict):
                    # Agent-to-agent: the realm switch, plus the defaults agents inherit. Unlike
                    # the per-agent block, these are the floor — there's nothing below to fall back
                    # to — so they're written as given rather than cleared when unrecognised.
                    from .. import inbox as _inbox
                    cur = cfg.get("inbox") or {}
                    cur["enabled"] = bool(body["inbox"].get("enabled", True))
                    cad = str(body["inbox"].get("cadence", ""))
                    acc = str(body["inbox"].get("accepts", ""))
                    if cad in _inbox.CADENCES:
                        cur["cadence"] = cad
                    if acc in _inbox.ACCEPTS:
                        cur["accepts"] = acc
                    cfg["inbox"] = cur
                if isinstance(body.get("notifications"), dict):
                    # The event × channel grid. Written whole so unticking the last box in a row
                    # persists as "off" rather than falling back to the default and switching
                    # itself back on.
                    from .. import notify as _notify
                    incoming = (body["notifications"].get("matrix") or {})
                    grid = {}
                    for ev in _notify.EVENTS:
                        row = incoming.get(ev) or {}
                        grid[ev] = {c: bool(row.get(c, False)) for c in _notify.CHANNELS}
                    n = {k: v for k, v in (cfg.get("notifications") or {}).items()
                         if k not in _notify.EVENTS and k != "enabled"}   # drop the legacy shape
                    n["matrix"] = grid
                    # May this realm interrupt you while you're looking at another one? Stored
                    # both ways round rather than only when off: the default is on, and a realm
                    # that has been deliberately switched off should stay off if the default
                    # ever changes.
                    xr = body["notifications"].get("cross_realm")
                    if xr is not None:
                        n["cross_realm"] = bool(xr)
                    cfg["notifications"] = n
                util.write_json_atomic(rj, cfg)
            icon = (body.get("icon") or "").strip()
            if icon:  # a Lucide icon name chosen from the picker -> theme.json + drop any uploaded image
                tj = Path(self.realm) / "theme.json"
                theme = json.loads(tj.read_text(encoding="utf-8-sig")) if tj.exists() else {}
                theme["icon"] = icon
                util.write_json_atomic(tj, theme)
                for old in Path(self.realm).glob("icon.*"):
                    old.unlink()
            # The timezone lives in the System memory every agent reads, so it has to be rebuilt
            # here too — not only when user settings are saved.
            self._refresh_system("realm-settings")
            return {"ok": True}
        except Exception as e:  # noqa
            swallowed(log, '_save_realm_settings: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _upload_realm_icon(self, body: dict) -> dict:
        try:
            return self._write_data_image(Path(self.realm) / "icon", body.get("data", ""))
        except Exception as e:  # noqa
            swallowed(log, '_upload_realm_icon: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _realm_archive(self, body: dict) -> dict:
        """Drop a realm from ARMADA's list. Touches no files — the folder stays where it is and can
        be added back with the realm picker."""
        path = str(body.get("path") or "").strip()
        if not path:
            return {"ok": False, "error": "no path"}
        target = str(Path(path).resolve())
        if target == str(Path(self.realm).resolve()):
            return {"ok": False, "error": "That's the realm you're using. Switch to another first."}
        items = _reg_load()
        kept = [i for i in items if str(Path(i.get("path", "")).resolve()) != target]
        if len(kept) == len(items):
            return {"ok": False, "error": "That realm isn't in the list."}
        _reg_save(kept)
        return {"ok": True, "remaining": len(kept)}

    def _adopt_release(self, body: dict) -> dict:
        """The owner has read what an adopted realm will run and allows it (5.8c)."""
        from .. import preflight
        path = str(body.get("path") or self.realm)
        if not activerealm.is_realm(path):
            return {"ok": False, "error": "not a realm"}
        pf = preflight.release_adopt_review(path)
        return {"ok": True, "held": pf.get("held"), "summary": pf.get("summary")}

    def _realm_preflight(self, body: dict) -> dict:
        """Can this realm run here? Holds or releases its scheduler as a side effect, so the answer
        and the consequence can't disagree."""
        from .. import preflight
        target = str(body.get("path") or self.realm)
        engine = str(body.get("engine") or "claude")
        res = preflight.apply_hold(target, engine)
        # detect_root gives the UI something to offer when the workspace is the problem.
        from .. import workspace as ws
        if any(c["id"] == "workspace" and not c["ok"] for c in res["checks"]):
            res["suggested_root"] = ws.detect_root(target)
        return res

    def _save_covenant(self, body: dict) -> dict:
        """Write the realm's Covenant (tenets.md). Loaded into every agent's context, so this is
        the highest-leverage text in the realm — and the owner's to write, unlike System memory."""
        text = str(body.get("text") or "")
        if len(text) > 40_000:
            return {"ok": False, "error": "Too long — keep the Covenant under 40,000 characters."}
        try:
            util.write_text_atomic(Path(self.realm) / "tenets.md", text)
        except OSError as e:
            return {"ok": False, "error": str(e)[:200]}
        return {"ok": True, "chars": len(text)}

    def _set_approot(self, body: dict) -> dict:
        """Set the one folder on this machine ARMADA works in. Re-checks the current realm after,
        since moving the root can put the realm you're looking at outside it."""
        from .. import approot, preflight
        root = str(body.get("root") or "").strip()
        if body.get("create") and root:
            # The first-run page suggests ~/ARMADA, which usually doesn't exist yet. Only on an
            # explicit ask, and only a folder whose parent already exists — a typo shouldn't
            # quietly build a tree of folders somewhere unexpected.
            try:
                rp = Path(root)
                if rp.is_absolute() and not rp.exists() and rp.parent.is_dir():
                    rp.mkdir()
            except OSError as e:
                return {"ok": False, "error": f"Couldn't create {root}: {e}"[:200]}
        r = approot.set_root(root)
        if not r.get("ok"):
            return r
        if self.realm:                      # none yet on the first-run page
            r["preflight"] = preflight.apply_hold(self.realm)
        return r

    _BAD_NAME_CHARS = '<>:"/\\|?*'

    def _first_realm(self, body: dict) -> dict:
        """The first-run page's Create: a realm named `name`, in a folder of that name inside the
        app root. The page never asks for a path — choosing where the first realm lives is a
        question a new user can't answer yet, and the root already answers it."""
        from .. import approot
        name = " ".join(str(body.get("name") or "").split())[:60]
        if not name:
            return {"ok": False, "error": "Give it a name."}
        if not approot.exists():
            return {"ok": False, "error": "Choose ARMADA’s folder first (step 1)."}
        folder = "".join(c for c in name if c not in self._BAD_NAME_CHARS and ord(c) >= 32).strip(" .")
        if not folder:
            return {"ok": False, "error": "Use some letters or numbers in the name."}
        base = Path(approot.root())
        p, n = base / folder, 2
        while p.exists():
            p, n = base / f"{folder} {n}", n + 1
        return self._new_realm({"mode": "create", "name": name, "path": str(p),
                                "template": str(body.get("template") or "scratch")})

    def _set_workspace(self, body: dict) -> dict:
        """Point the realm at its workspace folder on this machine, then re-check."""
        from .. import preflight, workspace as ws
        target = str(body.get("path") or self.realm)
        root = str(body.get("workspace") or "").strip()
        if root and not Path(root).is_dir():
            return {"ok": False, "error": f"{root} isn't a folder on this machine."}
        r = ws.set_root(target, root)
        r["preflight"] = preflight.apply_hold(target)     # fixing it must lift the hold immediately
        return r

    def _workspace_migrate(self, body: dict) -> dict:
        """Rewrite literal workspace paths in this realm's jobs as {workspace}.

        Previews unless apply is true, because it edits the owner's own prompt text.
        """
        from .. import workspace as ws
        target = str(body.get("path") or self.realm)
        old = str(body.get("old_root") or "").strip() or ws.detect_root(target)
        return ws.migrate(target, old, apply=bool(body.get("apply")))

    def _realm_export(self, body: dict) -> dict:
        from .. import realmops
        r = realmops.export(str(body.get("path") or self.realm))
        if r.get("ok"):
            self._reveal({"path": r["path"]})      # show them the zip straight away
        return r

    def _realm_delete(self, body: dict) -> dict:
        """Delete a realm's files. Requires the realm's folder name typed back as confirmation —
        this is the most destructive thing ARMADA can do, so a mis-click can't reach it."""
        from .. import realmops
        path = str(body.get("path") or "").strip()
        confirm = str(body.get("confirm") or "").strip()
        if not path:
            return {"ok": False, "error": "no path"}
        p = Path(path)
        if confirm.lower() != p.name.lower():
            return {"ok": False, "error": f'Type "{p.name}" to confirm.'}
        r = realmops.delete(p, current_realm=self.realm)
        if r.get("ok"):
            target = str(p.resolve())
            _reg_save([i for i in _reg_load()
                       if str(Path(i.get("path", "")).resolve()) != target])
        return r

