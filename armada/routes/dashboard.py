"""The Overview dashboard's sections/widgets, usage, memory, goals, and inbox.

These don't map onto one of the plan's six named areas on their own, but they're
cohesive as "the realm-content tabs", and none is big enough alone to warrant its own
module.

Split out of serve.py (Phase 2, 2.3) — a pure move, no behaviour change; the route table
stays in serve.py, only the handler bodies moved.
"""
from __future__ import annotations
import http.server, io, json, logging, os, subprocess, sys, threading, time, urllib.parse, contextlib
from pathlib import Path
from .. import activerealm, reader, render, scheduler, util, brand
from ..util import safe_seg
from ..assets import ANCHOR_SCROLL_JS as _ANCHOR_SCROLL_JS  # Phase 2, 2.1
from . import _shared
from ..util import swallowed

log = logging.getLogger("armada.serve")


class DashboardRoutes:
    def _get_add_section(self):
        from .. import webui
        self._send(200, webui.render_add_section(reader.read(self.realm), dark=self._dark()))

    def _get_edit_section(self, path):
        from .. import webui
        try:
            idx = int(path.rsplit("/", 1)[1])
        except ValueError:
            idx = -1
        self._send(200, webui.render_edit_section(reader.read(self.realm), idx, dark=self._dark()))

    def _get_section(self, path):
        from .. import webui
        try:
            idx = int(path.rsplit("/", 1)[1])
        except ValueError:
            idx = -1
        self._send(200, webui.render_section(reader.read(self.realm), idx, dark=self._dark()))

    def _get_usage(self):
        q = self._query()
        self._json(200, self._usage_api(q.get("mode", "line"), q.get("window", ""), q.get("by", "agents")))

    def _get_usage_limits(self):
        # Real Claude subscription usage (session 5h + weekly) for the widget's limit bars. Read-only
        # and best-effort — usage_api.fetch() never raises; on any problem it returns available:False.
        # The realm is passed so a good reading can be banked there and replayed (with its age)
        # when the token has lapsed — a stale figure beats a blank header.
        from .. import usage_api
        try:
            self._json(200, usage_api.fetch(self.realm))
        except Exception as e:  # noqa — must never break page chrome
            swallowed(log, '_get_usage_limits: failed; reported to the caller')
            self._json(200, {"available": False, "reason": "error", "detail": str(e)[:120]})

    def _delete_memory(self, body: dict) -> dict:
        base = (Path(self.realm) / "agents" / safe_seg(body.get("agent"), "agent") / "memory") if body.get("scope") == "agent" \
            else (Path(self.realm) / "memory")
        name = self._slug(body.get("name", ""))
        f = base / f"{name}.md"
        if ".." in str(body.get("name", "")) or not f.is_file():
            return {"ok": False, "error": "not found"}
        try:
            f.unlink(); return {"ok": True}
        except Exception as e:  # noqa
            swallowed(log, '_delete_memory: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _add_memory(self, body: dict) -> dict:
        scope = body.get("scope", "realm")
        title = (body.get("title") or "").strip()
        text = (body.get("text") or "").strip()
        if not text:
            return {"ok": False, "error": "memory text required"}
        if scope == "agent":
            base = Path(self.realm) / "agents" / safe_seg(body.get("agent"), "agent") / "memory"
            if not base.parent.is_dir():
                return {"ok": False, "error": f"no agent {body.get('agent')}"}
        else:
            base = Path(self.realm) / "memory"
        base.mkdir(parents=True, exist_ok=True)
        edit = self._slug(body.get("name", "")) if body.get("name") else ""
        if edit and (base / f"{edit}.md").exists():
            f = base / f"{edit}.md"                       # edit-in-place: keep the filename
        else:
            slug = self._slug(title or text[:40]) or "note"
            f = base / f"{slug}.md"
            n = 2
            while f.exists():
                f = base / f"{slug}-{n}.md"; n += 1
        try:
            # preserve existing frontmatter (e.g. kind: core) when editing in place
            from .. import memory as _memory
            meta = {}
            if f.exists():
                try:
                    meta, _ = _memory._frontmatter(f.read_text(encoding="utf-8-sig"))
                except Exception:  # noqa
                    swallowed(log, '_add_memory: failed; using a default')
                    meta = {}
            if title:
                meta["title"] = title
            # stamp who/when (UI edits are the owner; an agent path would pass its own id via 'by')
            import datetime as _dt
            meta["updated_by"] = (body.get("by") or "owner").strip()
            meta["updated"] = _dt.date.today().isoformat()
            fm = ""
            if meta:
                keys = (["title"] if "title" in meta else []) + [k for k in meta if k != "title"]
                fm = "---\n" + "".join(f"{k}: {meta[k]}\n" for k in keys) + "---\n"
            util.write_text_atomic(f, fm + text + "\n")
            return {"ok": True}
        except Exception as e:  # noqa
            swallowed(log, '_add_memory: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _add_goal(self, body: dict) -> dict:
        from .. import goals
        title = (body.get("title") or "").strip()
        if not title:
            return {"ok": False, "error": "a title is required"}
        stem = body.get("stem") or None
        ags = body.get("agents")
        ags = [safe_seg(a, "agent") for a in ags] if isinstance(ags, list) else None
        try:
            if stem:
                stem = safe_seg(stem, "goal")
            s = goals.save_goal(self.realm, title=title, body=(body.get("body") or ""),
                                status=(body.get("status") or ""), target=(body.get("target") or ""),
                                agents=ags, stem=stem)
            self._refresh_system("goal-saved")
            return {"ok": True, "stem": s}
        except Exception as e:  # noqa
            swallowed(log, '_add_goal: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _delete_goal(self, body: dict) -> dict:
        from .. import goals
        try:
            ok = goals.delete_goal(self.realm, safe_seg(body.get("stem"), "goal"))
            if ok:
                self._refresh_system("goal-deleted")
            return {"ok": ok, "error": None if ok else "not found"}
        except Exception as e:  # noqa
            swallowed(log, '_delete_goal: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _set_goal_agents(self, body: dict) -> dict:
        """Add/remove/toggle one owner on a goal. action: 'add' (drag), 'remove' (chip ×),
        or 'toggle' (default). The coordinator is always an owner and isn't stored here."""
        from .. import goals
        try:
            stem = safe_seg(body.get("stem"), "goal")
            agent = safe_seg(body.get("agent"), "agent")
            action = body.get("action", "toggle")
            g = goals.get_goal(self.realm, stem)
            if not g:
                return {"ok": False, "error": "no such goal"}
            cur = list(g["agents"])
            has = agent in cur
            if action == "add" or (action == "toggle" and not has):
                if not has:
                    cur.append(agent)
            elif action == "remove" or (action == "toggle" and has):
                if has:
                    cur.remove(agent)
            goals.set_agents(self.realm, stem, cur)
            self._refresh_system("goal-owners")
            return {"ok": True, "agents": cur}
        except Exception as e:  # noqa
            swallowed(log, '_set_goal_agents: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _add_section(self, body: dict) -> dict:
        name, src = (body.get("name") or "").strip(), (body.get("src") or "").strip()
        if not name or not src:
            return {"ok": False, "error": "name and source required"}
        rj = Path(self.realm) / "realm.json"
        if not rj.exists():
            return {"ok": False, "error": "sections need a native realm (realm.json)"}
        try:
            with util.file_lock(rj):
                cfg = json.loads(rj.read_text(encoding="utf-8-sig"))
                sections = cfg.get("sections", [])
                entry = {"name": name, ("url" if src.lower().startswith("http") else "path"): src}
                sections.append(entry)
                cfg["sections"] = sections
                util.write_json_atomic(rj, cfg)
            return {"ok": True, "index": len(sections) - 1}
        except Exception as e:  # noqa
            swallowed(log, '_add_section: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _add_widget_section(self, body: dict) -> dict:
        """Promote a dashboard widget to its own nav section. De-dupes: one section per widget id."""
        wid = (body.get("widget") or "").strip()
        name = (body.get("name") or "").strip()
        if not wid:
            return {"ok": False, "error": "widget required"}
        rj = Path(self.realm) / "realm.json"
        if not rj.exists():
            return {"ok": False, "error": "sections need a native realm (realm.json)"}
        try:
            with util.file_lock(rj):
                cfg = json.loads(rj.read_text(encoding="utf-8-sig"))
                sections = cfg.get("sections", [])
                for i, s in enumerate(sections):
                    if isinstance(s, dict) and s.get("widget") == wid:
                        return {"ok": True, "index": i, "existing": True}
                sections.append({"name": name or wid.title(), "widget": wid})
                cfg["sections"] = sections
                util.write_json_atomic(rj, cfg)
            return {"ok": True, "index": len(sections) - 1}
        except Exception as e:  # noqa
            swallowed(log, '_add_widget_section: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _sections_rw(self):
        rj = Path(self.realm) / "realm.json"
        cfg = json.loads(rj.read_text(encoding="utf-8-sig")) if rj.exists() else {}
        return rj, cfg, cfg.get("sections", [])

    def _update_section(self, body: dict) -> dict:
        try:
            i = int(body.get("index", -1))
        except (TypeError, ValueError):
            return {"ok": False, "error": "bad index"}
        name, src = (body.get("name") or "").strip(), (body.get("src") or "").strip()
        if not name or not src:
            return {"ok": False, "error": "name and source required"}
        rj = Path(self.realm) / "realm.json"
        try:
            with util.file_lock(rj):
                _rj, cfg, sections = self._sections_rw()
                if i < 0 or i >= len(sections):
                    return {"ok": False, "error": "no such section"}
                newsec = {"name": name, ("url" if src.lower().startswith("http") else "path"): src}
                prev = sections[i] if isinstance(sections[i], dict) else {}
                for k in ("snapshot", "source", "url"):  # preserve mirror config across a name/src edit
                    if k in prev and k not in newsec:
                        newsec[k] = prev[k]
                sections[i] = newsec
                cfg["sections"] = sections
                util.write_json_atomic(rj, cfg)
            return {"ok": True}
        except Exception as e:  # noqa
            swallowed(log, '_update_section: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _delete_section(self, body: dict) -> dict:
        try:
            i = int(body.get("index", -1))
        except (TypeError, ValueError):
            return {"ok": False, "error": "bad index"}
        rj = Path(self.realm) / "realm.json"
        try:
            with util.file_lock(rj):
                _rj, cfg, sections = self._sections_rw()
                if i < 0 or i >= len(sections):
                    return {"ok": False, "error": "no such section"}
                sections.pop(i); cfg["sections"] = sections
                util.write_json_atomic(rj, cfg)
            return {"ok": True}
        except Exception as e:  # noqa
            swallowed(log, '_delete_section: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _rename_section(self, body: dict) -> dict:
        """Rename in place — change only the display name, preserving url/path/widget/snapshot."""
        try:
            i = int(body.get("index", -1))
        except (TypeError, ValueError):
            return {"ok": False, "error": "bad index"}
        name = (body.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "name required"}
        rj = Path(self.realm) / "realm.json"
        try:
            with util.file_lock(rj):
                _rj, cfg, sections = self._sections_rw()
                if i < 0 or i >= len(sections):
                    return {"ok": False, "error": "no such section"}
                if isinstance(sections[i], dict):
                    sections[i]["name"] = name
                else:
                    sections[i] = {"name": name, "path": str(sections[i])}
                cfg["sections"] = sections
                util.write_json_atomic(rj, cfg)
            return {"ok": True}
        except Exception as e:  # noqa
            swallowed(log, '_rename_section: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _reorder_sections(self, body: dict) -> dict:
        """Reorder to the given index permutation (list of original indices, new order)."""
        order = body.get("order")
        if not isinstance(order, list):
            return {"ok": False, "error": "order required"}
        rj = Path(self.realm) / "realm.json"
        try:
            with util.file_lock(rj):
                _rj, cfg, sections = self._sections_rw()
                try:
                    idx = [int(x) for x in order]
                except (TypeError, ValueError):
                    return {"ok": False, "error": "bad order"}
                if sorted(idx) != list(range(len(sections))):
                    return {"ok": False, "error": "order must be a permutation of all sections"}
                cfg["sections"] = [sections[i] for i in idx]
                util.write_json_atomic(rj, cfg)
            return {"ok": True}
        except Exception as e:  # noqa
            swallowed(log, '_reorder_sections: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _snapshot_refresh(self, section: dict, force: bool = False):
        """Keep a section's local snapshot (inside the realm) fresh from its `source`.
        source = a local file/glob (newest wins) or an http(s) URL. Serving the local copy
        means external firewalls / cross-origin iframe 'verifying…' challenges never bite."""
        snap = section.get("snapshot")
        src = section.get("source")
        if not snap or not src:
            return
        root = Path(self.realm).resolve()
        dest = (Path(self.realm) / snap).resolve()
        if not str(dest).startswith(str(root)):    # snapshot must live inside the realm
            return

        def _newest(pattern):
            import glob as _glob
            cands = _glob.glob(pattern) if any(c in str(pattern) for c in "*?[") else [pattern]
            files = [Path(c) for c in cands if Path(c).is_file()]
            return max(files, key=lambda p: p.stat().st_mtime) if files else None
        try:
            content = None
            if isinstance(src, str) and src.lower().startswith(("http://", "https://")):
                if not force and dest.exists():
                    return                          # URL sources refresh only on demand (button)
                import urllib.request
                req = urllib.request.Request(src, headers={"User-Agent": "ARMADA/1.0"})
                content = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
            else:
                nf = _newest(src)
                if not nf:
                    return
                if not force and dest.exists() and nf.stat().st_mtime <= dest.stat().st_mtime:
                    return                          # snapshot already up to date
                content = nf.read_text(encoding="utf-8-sig", errors="replace")
            if content is None:
                return
            # a bare content fragment (no <html>) is wrapped into a styled standalone doc so it
            # renders correctly on its own — inline the section's stylesheet if one is configured.
            if "<html" not in content.lower():
                css = ""
                cssref = section.get("css")
                cf = _newest(cssref) if cssref else None
                if cf:
                    css = cf.read_text(encoding="utf-8-sig", errors="replace")
                content = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                           '<meta name="viewport" content="width=device-width, initial-scale=1">'
                           + (f"<style>{css}</style>" if css else "")
                           + "</head><body>" + content + "</body></html>")
            util.write_text_atomic(dest, content)
        except Exception:  # noqa — a stale/missing snapshot just falls back to the URL
            log.debug('_snapshot_refresh: failed; ignored', exc_info=True)

    def _section_snapshot(self, body: dict) -> dict:
        from .. import reader
        try:
            i = int(body.get("index", body.get("idx", -1)))
        except (TypeError, ValueError):
            return {"ok": False, "error": "bad index"}
        sections = getattr(reader.read(self.realm), "sections", []) or []
        if i < 0 or i >= len(sections):
            return {"ok": False, "error": "no such section"}
        s = sections[i]
        if not (isinstance(s, dict) and s.get("snapshot")):
            return {"ok": False, "error": "section has no local snapshot"}
        self._snapshot_refresh(s, force=True)
        dest = Path(self.realm) / s["snapshot"]
        return {"ok": dest.is_file(), "ts": int(dest.stat().st_mtime) if dest.is_file() else 0}

    def _section_asset(self, path: str):
        """Serve a file from an 'app section's local asset directory (sandboxed to that dir),
        so a mini-site (shell + css + js + data) renders same-origin — its own header, edition
        picker and theme toggle all work, with no external firewall in the way."""
        from .. import reader
        rest = path[len("/section-asset/"):]
        head, _, rel = rest.partition("/")
        try:
            idx = int(head)
        except ValueError:
            self._send(404, "bad section", "text/plain"); return
        sections = getattr(reader.read(self.realm), "sections", []) or []
        if idx < 0 or idx >= len(sections) or not isinstance(sections[idx], dict):
            self._send(404, "no section", "text/plain"); return
        base = sections[idx].get("assets")
        if not base:
            self._send(404, "no assets", "text/plain"); return
        base = Path(base).resolve()
        rel = urllib.parse.unquote(rel.split("?", 1)[0])
        target = (base / rel).resolve()
        if not str(target).startswith(str(base)) or not target.is_file() or target.suffix.lower() == ".php":
            self._send(404, "not found", "text/plain"); return
        self._send(200, target.read_bytes(), self._CT.get(target.suffix.lower(), "application/octet-stream"))

    def _section_raw(self, path: str):
        from .. import reader
        try:
            idx = int(path.rsplit("/", 1)[1])
        except ValueError:
            idx = -1
        sections = getattr(reader.read(self.realm), "sections", []) if True else []
        if idx < 0 or idx >= len(sections):
            self._send(404, "no section", "text/plain")
            return
        s = sections[idx]
        # 0) 'app section' — a local mini-site (shell + assets). Serve its entry with an injected
        #    <base> so relative css/js/data resolve to /section-asset/<idx>/, plus a tiny shim so
        #    in-page #anchors still scroll (rather than navigating away under the base).
        if isinstance(s, dict) and s.get("assets") and s.get("entry"):
            base = Path(s["assets"]).resolve()
            entry = (base / s["entry"]).resolve()
            if str(entry).startswith(str(base)) and entry.is_file():
                htmltext = entry.read_text(encoding="utf-8-sig", errors="replace")
                inject = (f'<base href="/section-asset/{idx}/">' + _ANCHOR_SCROLL_JS)
                low = htmltext.lower()
                pos = low.find("<head")
                if pos != -1:
                    pos = low.find(">", pos) + 1
                    htmltext = htmltext[:pos] + inject + htmltext[pos:]
                else:
                    htmltext = inject + htmltext
                self._send(200, htmltext.encode("utf-8"), "text/html; charset=utf-8")
                return
        # 1) local snapshot (mirror) wins — served same-origin, no iframe/firewall issues
        if isinstance(s, dict) and s.get("snapshot"):
            self._snapshot_refresh(s)              # lazy: pull newest from source if stale
            snap = (Path(self.realm) / s["snapshot"]).resolve()
            if str(snap).startswith(str(Path(self.realm).resolve())) and snap.is_file():
                self._send(200, snap.read_bytes(), "text/html; charset=utf-8")
                return
            # no snapshot yet → fall through to the live URL if there is one
        if isinstance(s, dict) and s.get("url"):
            self.send_response(302); self.send_header("Location", s["url"]); self.end_headers()
            return
        rel = (s.get("path") if isinstance(s, dict) else "") or ""
        f = (Path(self.realm) / rel).resolve()
        if ".." in rel or not str(f).startswith(str(Path(self.realm).resolve())) or not f.is_file():
            self._send(404, "file not found in realm", "text/plain")
            return
        ct = "text/html; charset=utf-8" if f.suffix.lower() in (".html", ".htm") else \
             ("text/markdown; charset=utf-8" if f.suffix.lower() == ".md" else "text/plain; charset=utf-8")
        self._send(200, f.read_bytes(), ct)

    def _inbox_unread(self, body: dict) -> dict:
        """Put a handled message back in the waiting pile so it runs again on the next pass."""
        from .. import inbox
        return inbox.requeue(self.realm, str(body.get("agent", "")), str(body.get("id", "")))

    def _inbox_process(self, body: dict) -> dict:
        """Run a waiting message now instead of waiting for the agent's cadence."""
        from .. import runner
        return runner.process_message_now(self.realm, str(body.get("agent", "")),
                                          str(body.get("id", "")))

    def _inbox_delete(self, body: dict) -> dict:
        from .. import inbox
        return inbox.delete(self.realm, str(body.get("agent", "")), str(body.get("id", "")))

    def _save_dashboard(self, body: dict) -> dict:
        # NOTE: the grid is 20 columns (5% each); spans run 4..20 (min 4 = 20% wide). span_scale:20 must
        # be persisted so _load_dashboard doesn't re-run its ×5 legacy migration and blow widths up on reload.
        d = {
            "single": {str(k): bool(v) for k, v in (body.get("single") or {}).items()},
            "order": [str(x) for x in (body.get("order") or [])],
            "spans": {str(k): max(4, min(20, int(v))) for k, v in (body.get("spans") or {}).items()},
            "heights": {str(k): max(120, min(3000, int(v))) for k, v in (body.get("heights") or {}).items()},
            "threads": [],
            "span_scale": 20,
        }
        for w in (body.get("threads") or []):
            try:
                a = safe_seg(w.get("agent"), "agent")
                t = safe_seg(w.get("thread"), "thread")
            except util.UnsafeSegment:
                continue
            d["threads"].append({
                "agent": a, "agentDisp": str(w.get("agentDisp") or a),
                "thread": t, "threadTitle": str(w.get("threadTitle") or t),
                "span": max(4, min(20, int(w.get("span") or 10))), "unread": bool(w.get("unread")),
            })
        with util.file_lock(Path(self.realm) / "dashboard.json"):   # _load_dashboard's migration takes it too
            util.write_json_atomic(Path(self.realm) / "dashboard.json", d)
        return {"ok": True}

    def _usage_api(self, mode: str, window: str, by: str = "agents") -> dict:
        from .. import webui
        try:
            realm = reader.read(self.realm)
            return webui._usage_data(realm, self.realm, mode, window, by)
        except Exception as e:  # noqa
            swallowed(log, '_usage_api: failed; error returned to the caller')
            return {"error": str(e), "mode": mode, "window": window}

