"""Agents, their threads and chat.

new/save/retire/reinstate/delete an agent, avatar management, thread listing/turns/rail/
truncate/new-thread/autoname, chat + chat-stream + chat-stop, run, reveal, job proposals.

Split out of serve.py (Phase 2, 2.3) — a pure move, no behaviour change; the route table
stays in serve.py, only the handler bodies moved.
"""
from __future__ import annotations
import http.server, io, json, logging, os, subprocess, sys, threading, time, urllib.parse, contextlib
from pathlib import Path
from .. import activerealm, reader, render, scheduler, util, brand
from ..util import safe_seg
from . import _shared
from ._shared import _derive_title, _llm_title
from ..util import swallowed

log = logging.getLogger("armada.serve")


class AgentRoutes:
    def _get_chat_stop(self):
        self._json(200, self._chat_stop(self._query()))

    def _get_retired_agents(self):
        """Who could be brought back, and what they were. Feeds the Appoint modal's Reinstate tab,
        which fills its form from this rather than making anyone retype a settled agent."""
        from .. import agentops
        self._json(200, {"agents": agentops.list_retired(self.realm)})

    def _get_new_agent(self):
        from .. import webui
        self._send(200, webui.render_new_agent(reader.read(self.realm), self.realm, dark=self._dark()))

    def _get_agent(self, path):
        from .. import webui
        parts = [p for p in path.split("/") if p]      # ['agent', '<id>', '<subtab>?']
        aid = safe_seg(parts[1], "agent") if len(parts) > 1 else ""
        subtab = parts[2] if len(parts) > 2 else "threads"
        try:
            self._send(200, webui.render_agent(reader.read(self.realm), self.realm, aid, subtab,
                                               dark=self._dark(), query=self._query()))
        except SystemExit as e:
            self._err_page(e)

    def _get_embed_thread(self):
        from .. import webui
        q = self._query()
        try:
            self._send(200, webui.render_thread_embed(
                reader.read(self.realm), self.realm, safe_seg(q.get("agent", ""), "agent"),
                safe_seg(q.get("thread", "main"), "thread"), dark="dark" in q))
        except SystemExit as e:
            self._err_page(e, bare=True)

    def _get_threads(self):
        q = self._query()
        self._json(200, self._threads_list(safe_seg(q.get("agent", ""), "agent")))

    def _get_proposals_count(self):
        from .. import jobs as jobs_mod
        try:
            n = jobs_mod.count_pending(self.realm)
        except Exception:  # noqa
            swallowed(log, '_get_proposals_count: failed; using a default')
            n = 0
        self._json(200, {"count": n})

    def _get_agent_activity(self):
        """Live activity state per agent ({id: 'working'|'input'|'unseen'|'idle'}) so the dashboard
        can refresh the status dots without a full reload."""
        from .. import webui
        try:
            realm = reader.read(self.realm)
            out = {a.id: webui._agent_activity(self.realm, a.id) for a in realm.agents}
        except Exception:  # noqa
            swallowed(log, '_get_agent_activity: failed; using a default')
            out = {}
        self._json(200, out)

    def _get_thread_turns(self):
        from .. import webui
        q = self._query()
        self._send(200, webui.render_thread_turns(reader.read(self.realm), self.realm,
                                                  safe_seg(q.get("agent", ""), "agent"),
                                                  safe_seg(q.get("thread", "main"), "thread")))

    def _get_thread_rail(self):
        from .. import webui
        q = self._query()
        self._send(200, webui.render_thread_rail(reader.read(self.realm), self.realm,
                                                 safe_seg(q.get("agent", ""), "agent"),
                                                 safe_seg(q.get("thread", "main"), "thread")))

    def _get_avatar(self, path):
        aid = safe_seg(path[len("/avatar/"):].strip("/"), "agent")
        from .. import webui
        f = webui._avatar_file(self.realm, aid)
        if f and f.is_file():
            self._send(200, f.read_bytes(), self._CT.get(f.suffix.lower(), "image/png"))
        else:
            self._send(404, "no avatar", "text/plain")

    def _get_thread_file(self):
        q = self._query()
        name = str(q.get("name", ""))
        # a filename may carry an extension (dots), unlike a path segment — validate leniently
        # but block traversal/separators, and confine the resolved path to the attachments dir.
        name_ok = bool(name) and ".." not in name and "/" not in name and "\\" not in name \
            and "\x00" not in name and not name.startswith(".") \
            and all(c.isalnum() or c in "._-" for c in name)
        try:
            agent = safe_seg(q.get("agent", ""), "agent")
            thread = safe_seg(q.get("thread", "main"), "thread")
        except util.UnsafeSegment:
            self._send(400, "bad path", "text/plain")
            return
        if not name_ok:
            self._send(400, "bad name", "text/plain")
            return
        base = (Path(self.realm) / "agents" / agent / "threads" / thread / "attachments").resolve()
        f = (base / name).resolve()
        if base in f.parents and f.is_file() and f.suffix.lower() in self._CT:
            self._send(200, f.read_bytes(), self._CT.get(f.suffix.lower(), "application/octet-stream"))
        else:
            self._send(404, "no file", "text/plain")

    def _new_agent(self, body: dict) -> dict:
        disp = (body.get("display") or "").strip()
        if not disp:
            return {"ok": False, "error": "name required"}
        aid = self._slug(disp)
        adir = Path(self.realm) / "agents" / safe_seg(aid, "agent")
        if adir.exists():
            return {"ok": False, "error": f"agent '{aid}' already exists"}
        try:
            (adir / "jobs").mkdir(parents=True); (adir / "memory").mkdir()
            import datetime as _dt
            util.write_json_atomic(adir / "agent.json", {
                "id": aid, "display": disp, "leader": body.get("leader", ""), "role": body.get("role", ""),
                "coordinator": bool(body.get("coordinator")), "membership": "cabinet",
                "autonomy": body.get("autonomy", "propose"), "model": body.get("model") or None,
                "effort": body.get("effort") or None,
                "color": body.get("color") or None,
                "appointed": _dt.date.today().isoformat(),
                "mandate": "mandate.md", "soul": "soul.md",
            })
            util.write_text_atomic(adir / "mandate.md", (body.get("mandate") or f"You are {disp}.").rstrip() + "\n")
            util.write_text_atomic(adir / "soul.md", (body.get("soul") or "").rstrip() + "\n")
            util.write_text_atomic(adir / "skills.json", "[]")
            self._refresh_system("agent-appointed")
            return {"ok": True, "id": aid}
        except Exception as e:  # noqa
            swallowed(log, '_new_agent: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _upload_avatar(self, body: dict) -> dict:
        adir = Path(self.realm) / "agents" / safe_seg(body.get("agent"), "agent")
        if not adir.is_dir():
            return {"ok": False, "error": f"no agent {body.get('agent')}"}
        try:
            return self._write_data_image(adir / "avatar", body.get("data", ""))
        except Exception as e:  # noqa
            swallowed(log, '_upload_avatar: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _set_avatar_preset(self, body: dict) -> dict:
        import shutil
        adir = Path(self.realm) / "agents" / safe_seg(body.get("agent"), "agent")
        preset = str(body.get("preset", ""))
        src = Path(__file__).resolve().parent / "webui" / "static" / "avatars" / f"{preset}.png"
        if not adir.is_dir():
            return {"ok": False, "error": f"no agent {body.get('agent')}"}
        if ".." in preset or not src.is_file():
            return {"ok": False, "error": "unknown preset"}
        try:
            for old in adir.glob("avatar.*"):
                old.unlink()
            shutil.copyfile(src, adir / "avatar.png")
            return {"ok": True}
        except Exception as e:  # noqa
            swallowed(log, '_set_avatar_preset: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    # --- user (owner) settings + avatar ---

    def _agent_retire(self, body: dict) -> dict:
        from .. import agentops
        return agentops.retire(self.realm, str(body.get("agent") or ""))

    def _agent_reinstate(self, body: dict) -> dict:
        from .. import agentops
        # Only the fields the Reinstate form offers. Everything else in agent.json comes back
        # untouched — the point is to restore an agent, not to fill in a new one with their name.
        keys = ("display", "role", "leader", "color", "autonomy", "model", "effort")
        over = {k: body[k] for k in keys if k in body}
        return agentops.reinstate(self.realm, str(body.get("agent") or ""), over)

    def _agent_delete(self, body: dict) -> dict:
        from .. import agentops
        aid = str(body.get("agent") or "")
        # Same shape as deleting a realm: type the name. An agent folder is threads, memories and
        # months of run history, and a misclick here is not recoverable from inside the app.
        want = str(body.get("confirm") or "").strip().lower()
        disp = str(body.get("display") or aid).strip().lower()
        if want not in (aid.lower(), disp):
            return {"ok": False, "error": f'Type "{body.get("display") or aid}" to confirm.'}
        return agentops.delete(self.realm, aid)

    def _chat_stream(self, q: dict):
        """Server-Sent Events: stream the agent's intermediate steps for one chat turn."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        def emit(obj):
            try:
                self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode("utf-8"))
                self.wfile.flush()
            except Exception:  # noqa - client disconnected; keep the run going, just stop emitting
                log.debug('emit: failed; ignored', exc_info=True)
        tid = q.get("tid", "")

        def on_proc(p):
            if tid:
                self._streams[tid] = p
        # Live "working" marker so the activity dot pulses while an interactive chat runs (the runner
        # only writes .running markers for scheduled jobs; a chat turn otherwise looks idle).
        mark = None
        try:
            mark = (Path(self.realm) / "agents" / safe_seg(q.get("agent", ""), "agent")
                    / "runs" / ".running" / "_chat.json")
            mark.parent.mkdir(parents=True, exist_ok=True)
            # Which thread, not just "a chat". The dot only needs to know the agent is busy, but
            # the transcript needs to know whether the turn it is looking at is the live one —
            # otherwise every thread shows a spinner whenever the agent is working anywhere.
            mark.write_text(json.dumps({"kind": "chat",
                                        "thread": safe_seg(q.get("thread", "main"), "thread")}),
                            encoding="utf-8")
        except Exception:  # noqa
            swallowed(log, '_chat_stream: failed; using a default')
            mark = None
        try:
            from ..runner import chat_stream
            r = chat_stream(self.realm, q.get("agent", ""), q.get("thread", "main"),
                            q.get("message", ""), on_event=emit, engine="claude", on_proc=on_proc,
                            images=q.get("images") or [], files=q.get("files") or [],
                            allow_tools=True)   # thread chats are agentic: the agent can read, write
            #   (e.g. propose a job) and search while you talk to it. Job proposals still need approval.
            emit({"kind": "done", **r})
            if r.get("ok"):
                try:                              # flag the thread's new output as unseen (teal dot)
                    from .. import webui
                    webui._mark_thread_unread(
                        Path(self.realm) / "agents" / safe_seg(q.get("agent", ""), "agent"),
                        safe_seg(q.get("thread", "main"), "thread"))
                except Exception:  # noqa
                    log.exception("mark-thread-unread failed")
                # name a still-default 'New Chat' from the topic of the first prompt. Done AFTER the
                # 'done' event (the reply is already shown), then pushed as a 'rename' event, so the
                # short title-model call doesn't delay the visible reply.
                try:
                    nt = self._autoname_thread(q.get("agent", ""), q.get("thread", "main"), q.get("message", ""))
                    if nt:
                        emit({"kind": "rename", "thread_title": nt})
                except Exception:  # noqa
                    log.exception("auto-name thread failed")
        except Exception as e:  # noqa
            swallowed(log, '_chat_stream: failed; reported to the caller')
            emit({"kind": "error", "error": str(e)})
        finally:
            self._streams.pop(tid, None)
            if mark is not None:
                try:
                    mark.unlink()
                except OSError:
                    pass
        time.sleep(0.3)  # let the browser process 'done' and close, so EventSource won't auto-reconnect

    def _chat_stop(self, q: dict) -> dict:
        p = self._streams.get(q.get("tid", ""))
        if not p:
            return {"ok": True, "note": "no active turn"}
        try:
            p.kill()
            return {"ok": True}
        except Exception as e:  # noqa
            swallowed(log, '_chat_stop: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _thread_truncate(self, body: dict) -> dict:
        """Keep only the first `keep` messages of a thread (drops the rest) — powers
        'restart from here' and 'edit': the caller then re-sends the (possibly edited) message."""
        agent = str(body.get("agent", ""))
        thread = str(body.get("thread", "main"))
        try:
            keep = int(body.get("keep", 0))
        except (TypeError, ValueError):
            return {"ok": False, "error": "bad keep"}
        mf = Path(self.realm) / "agents" / safe_seg(agent, "agent") / "threads" / safe_seg(thread, "thread") / "messages.jsonl"
        if not mf.exists():
            return {"ok": True, "kept": 0}
        try:
            lines = [ln for ln in mf.read_text(encoding="utf-8-sig").splitlines() if ln.strip()]
            util.write_text_atomic(mf, "\n".join(lines[:max(0, keep)]) + ("\n" if keep > 0 and lines[:keep] else ""))
            return {"ok": True, "kept": min(keep, len(lines))}
        except Exception as e:  # noqa
            swallowed(log, '_thread_truncate: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _threads_list(self, agent: str) -> dict:
        from .. import webui
        adir = Path(self.realm) / "agents" / safe_seg(agent, "agent")
        if not adir.is_dir():
            return {"ok": False, "error": f"no agent {agent}", "threads": []}
        names, meta = webui._ordered_threads(adir)
        return {"ok": True, "threads": [{"slug": n, "title": webui._thread_title(meta, n)} for n in names]}

    def _thread_action(self, body: dict) -> dict:
        agent = str(body.get("agent", ""))
        action = str(body.get("action", ""))
        adir = Path(self.realm) / "agents" / safe_seg(agent, "agent") / "threads"
        if not adir.parent.is_dir():
            return {"ok": False, "error": f"no agent {agent}"}
        adir.mkdir(parents=True, exist_ok=True)
        mf = adir / "meta.json"
        with util.file_lock(mf):     # read-modify-write of the thread index (4.3 L5)
            meta = {"titles": {}, "pinned": {}, "unread": {}, "order": [], "archived": {}}
            if mf.exists():
                try:
                    meta.update(json.loads(mf.read_text(encoding="utf-8-sig")))
                except Exception:  # noqa
                    log.debug('_thread_action: failed; ignored', exc_info=True)
            slug = str(body.get("thread", ""))
            if action == "reorder":
                order = [str(s) for s in (body.get("order") or []) if str(s) != "main"]
                meta["order"] = order
            elif action == "pin":
                meta.setdefault("pinned", {})[slug] = True
            elif action == "unpin":
                if slug == "main":
                    return {"ok": False, "error": "the main thread cannot be unpinned"}
                meta.setdefault("pinned", {})[slug] = False
            elif action == "unread":
                meta.setdefault("unread", {})[slug] = True
            elif action == "read":
                meta.setdefault("unread", {})[slug] = False
            elif action == "rename":
                title = str(body.get("title", "")).strip()
                if not title:
                    return {"ok": False, "error": "title required"}
                meta.setdefault("titles", {})[slug] = title[:80]
            elif action == "archive":
                if slug == "main":
                    return {"ok": False, "error": "the main thread cannot be archived"}
                import datetime as _dt
                meta.setdefault("archived", {})[slug] = _dt.date.today().isoformat()
                if slug in meta.get("order", []):
                    meta["order"].remove(slug)
                meta.setdefault("pinned", {}).pop(slug, None)
            elif action == "unarchive":
                meta.setdefault("archived", {}).pop(slug, None)
            elif action == "delete":
                if slug == "main":
                    return {"ok": False, "error": "the main thread cannot be deleted"}
                import shutil
                tdir = adir / safe_seg(slug, "thread")
                if body.get("delete_artifacts"):
                    self._delete_thread_artifacts(agent, slug)   # remove output files this thread wrote
                if tdir.is_dir():
                    shutil.rmtree(tdir, ignore_errors=True)
                for k in ("titles", "pinned", "unread", "archived"):
                    meta.setdefault(k, {}).pop(slug, None)
                if slug in meta.get("order", []):
                    meta["order"].remove(slug)
            else:
                return {"ok": False, "error": f"unknown action {action}"}
            try:
                util.write_json_atomic(mf, meta)
                return {"ok": True}
            except Exception as e:  # noqa
                swallowed(log, '_thread_action: failed; error returned to the caller')
                return {"ok": False, "error": str(e)}

    def _delete_thread_artifacts(self, agent: str, slug: str) -> None:
        """Delete the output-artifact files a thread produced (paths recorded in its turns). Only
        touches files INSIDE the realm — never anything outside it. Best-effort."""
        try:
            from ..threads import Thread
            realm = Path(self.realm).resolve()
            adir = realm / "agents" / safe_seg(agent, "agent")
            th = Thread(adir, safe_seg(slug, "thread"))
            for m in th._messages():
                for o in (m.get("outputs") or []):
                    pth = o.get("path") if isinstance(o, dict) else None
                    if not pth:
                        continue
                    f = Path(pth)
                    f = f if f.is_absolute() else (realm / pth)
                    try:
                        f = f.resolve()
                    except Exception:  # noqa
                        log.debug('_delete_thread_artifacts: failed; skipping this one', exc_info=True)
                        continue
                    if str(f).startswith(str(realm)) and f.is_file():
                        f.unlink()
        except Exception:  # noqa — artifact cleanup must never block the thread delete
            log.exception("delete thread artifacts failed (%s/%s)", agent, slug)

    def _new_thread(self, body: dict) -> dict:
        import re
        agent = str(body.get("agent", ""))
        adir = Path(self.realm) / "agents" / safe_seg(agent, "agent")
        if not adir.is_dir():
            return {"ok": False, "error": f"no agent {agent}"}
        tbase = adir / "threads"
        raw = str(body.get("name", "")).strip()
        if raw:
            slug = re.sub(r"[^a-z0-9\- ]", "", raw.lower()).strip().replace(" ", "-")[:40] or "chat"
            if (tbase / slug).exists():
                return {"ok": False, "error": "a thread with that name already exists"}
        else:
            # instant new chat, like the Claude app — auto-name a fresh unique thread
            slug = "new-chat"
            n = 2
            while (tbase / slug).exists():
                slug = f"new-chat-{n}"; n += 1
        try:
            (tbase / slug).mkdir(parents=True)
            # place the new thread at the TOP of the secondary (non-main) list, not the bottom
            mf = tbase / "meta.json"
            with util.file_lock(mf):
                meta = {"titles": {}, "pinned": {}, "unread": {}, "order": [], "archived": {}}
                if mf.exists():
                    try:
                        meta.update(json.loads(mf.read_text(encoding="utf-8-sig")))
                    except Exception:  # noqa
                        log.debug('_new_thread: failed; ignored', exc_info=True)
                order = [s for s in (meta.get("order") or []) if s not in (slug, "main")]
                meta["order"] = [slug] + order
                try:
                    util.write_json_atomic(mf, meta)
                except OSError:
                    pass
            return {"ok": True, "thread": slug}
        except Exception as e:  # noqa
            swallowed(log, '_new_thread: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _autoname_thread(self, agent: str, thread: str, first_msg: str):
        """After the first exchange, give a still-default 'New Chat' thread a title derived from the
        prompt (like the Claude app). Only touches auto-named 'new-chat*' threads that the owner
        hasn't renamed; returns the new title or None. The owner can still rename afterwards."""
        thread = str(thread)
        if thread == "main" or not thread.startswith("new-chat"):
            return None
        try:
            adir = Path(self.realm) / "agents" / safe_seg(agent, "agent") / "threads"
        except util.UnsafeSegment:
            return None
        # a short topic summary from a cheap model (like the Claude app); fall back to a heuristic
        title = _llm_title(adir.parent, first_msg) or _derive_title(first_msg)
        if not title:
            return None
        mf = adir / "meta.json"
        with util.file_lock(mf):     # the model call above runs unlocked; only the RMW is held
            meta = {"titles": {}, "pinned": {}, "unread": {}, "order": [], "archived": {}}
            if mf.exists():
                try:
                    meta.update(json.loads(mf.read_text(encoding="utf-8-sig")))
                except Exception:  # noqa
                    log.debug('_autoname_thread: failed; ignored', exc_info=True)
            if (meta.get("titles", {}) or {}).get(thread):
                return None                         # already named (owner renamed, or we already did)
            meta.setdefault("titles", {})[thread] = title
            try:
                util.write_json_atomic(mf, meta)
            except Exception:  # noqa
                swallowed(log, '_autoname_thread: failed; returning a fallback')
                return None
        return title

    def _remove_avatar(self, body: dict) -> dict:
        adir = Path(self.realm) / "agents" / safe_seg(body.get("agent"), "agent")
        if not adir.is_dir():
            return {"ok": False, "error": f"no agent {body.get('agent')}"}
        try:
            removed = 0
            for old in adir.glob("avatar.*"):
                old.unlink(); removed += 1
            return {"ok": True, "removed": removed}
        except Exception as e:  # noqa
            swallowed(log, '_remove_avatar: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _save_agent(self, body: dict) -> dict:
        agent = body.get("agent")
        adir = Path(self.realm) / "agents" / safe_seg(agent, "agent")
        if not adir.is_dir():
            return {"ok": False, "error": f"no agent {agent}"}
        try:
            aj = adir / "agent.json"
            # Locked: capabilities.py writes grants into this same file under the same lock (4.3 L4).
            with util.file_lock(aj):
                ac = json.loads(aj.read_text(encoding="utf-8-sig")) if aj.exists() else {"id": agent}
                if body.get("display"):
                    ac["display"] = body["display"]
                for k in ("autonomy", "role", "leader", "inbox_frequency"):
                    if k in body:
                        ac[k] = body[k]
                if isinstance(body.get("inbox"), dict):
                    # Blank means "inherit the realm default", so an empty value clears the override
                    # rather than storing an invalid one.
                    from .. import inbox as _inbox
                    cur = ac.get("inbox") or {}
                    cad, acc = str(body["inbox"].get("cadence", "")), str(body["inbox"].get("accepts", ""))
                    if cad in _inbox.CADENCES:
                        cur["cadence"] = cad
                    else:
                        cur.pop("cadence", None)
                    if acc in _inbox.ACCEPTS:
                        cur["accepts"] = acc
                    else:
                        cur.pop("accepts", None)
                    # The master switch is stored only when off: on is the default, and writing it
                    # explicitly would pin every agent to today's default forever.
                    if "enabled" in body["inbox"]:
                        if body["inbox"].get("enabled"):
                            cur.pop("enabled", None)
                        else:
                            cur["enabled"] = False
                    ac["inbox"] = cur
                if "verbosity" in body:          # blank = inherit the realm default
                    from .. import verbosity as _verbosity
                    v = _verbosity.normalise(body.get("verbosity"))
                    if v:
                        ac["verbosity"] = v
                    else:
                        ac.pop("verbosity", None)
                for k in ("model", "effort", "color", "fallback_model"):
                    if body.get(k):
                        ac[k] = body[k]
                    else:
                        ac.pop(k, None)
                # Read-aloud was built and shelved before v1 (see docs/dev/VOICE_SHELVED.md). Agents
                # configured while it existed still carry the keys; drop them on the next save rather
                # than leaving settings in the file that nothing reads.
                for k in ("voice_enabled", "voice", "voice_provider", "voice_rate"):
                    ac.pop(k, None)
                if "max_budget_usd" in body:                  # Advanced: per-run spend cap ('' / 0 clears it)
                    try:
                        b = float(body["max_budget_usd"])
                    except (TypeError, ValueError):
                        b = 0.0
                    if b > 0:
                        ac["max_budget_usd"] = b
                    else:
                        ac.pop("max_budget_usd", None)
                util.write_json_atomic(aj, ac)
            if "mandate" in body:
                util.write_text_atomic(adir / ac.get("mandate", "mandate.md"), body["mandate"].rstrip() + "\n")
            if "soul" in body:
                util.write_text_atomic(adir / ac.get("soul", "soul.md"), body["soul"].rstrip() + "\n")
            if "tenets" in body:
                util.write_text_atomic(adir / "tenets.md", body["tenets"].rstrip() + "\n")
            # Saving keeps you on the page, so the three document fields have to go back to reading
            # mode without a reload — and the HTML for that comes from here, through the same _md()
            # the page itself used. Rendering the markdown in the browser instead would mean a
            # second renderer, quietly disagreeing with the server about the same text.
            from ..webui._base import _md as _render_md
            rendered = {f"c-{k}": _render_md(str(body.get(k) or "").strip())
                        for k in ("mandate", "soul", "tenets") if k in body}
            return {"ok": True, "path": f"agents/{agent}/", "display": ac.get("display", ""),
                    "rendered": rendered}
        except Exception as e:  # noqa
            swallowed(log, '_save_agent: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _job_proposal(self, body: dict) -> dict:
        """Approve or reject an agent-authored pending job proposal (owner action)."""
        from .. import jobs as jobs_mod
        agent, slug, action = body.get("agent"), body.get("slug"), body.get("action")
        if not agent or not slug or action not in ("approve", "reject"):
            return {"ok": False, "error": "need agent, slug, action(approve|reject)"}
        try:
            agent = safe_seg(agent, "agent")
        except util.UnsafeSegment:
            return {"ok": False, "error": "bad agent"}
        if action == "approve":
            return jobs_mod.approve(self.realm, agent, str(slug))
        return jobs_mod.reject(self.realm, agent, str(slug))

    def _chat(self, body: dict) -> dict:
        from ..runner import chat
        agent, thread, msg = body.get("agent"), body.get("thread", "main"), body.get("message", "")
        engine = body.get("engine", "claude")
        if not agent or not msg.strip():
            return {"ok": False, "output": "missing agent/message"}
        try:
            return chat(self.realm, agent, thread, msg, engine=engine)
        except SystemExit as e:
            return {"ok": False, "output": str(e)}
        except Exception as e:  # noqa
            swallowed(log, '_chat: failed; error returned to the caller')
            return {"ok": False, "output": f"{type(e).__name__}: {e}"}

