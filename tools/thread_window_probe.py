"""Hidden WebView2 check of production thread windows using only a synthetic realm.

Run with a Python environment containing pywebview:
  python tools/thread_window_probe.py --output <result.json>
No provider is called; the deterministic reply transport exercises the saved thread.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import traceback
from unittest.mock import patch


def run(output):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import webview
    from armada import app, local_auth, serve, util, runner
    from armada.request_context import RealmContext
    from armada.threads import Thread
    from tests.golden_support import build_fixture

    result = {"ok": False, "checks": []}
    windows = []
    release = threading.Event()
    started = threading.Event()
    with tempfile.TemporaryDirectory(prefix="armada-thread-window-", ignore_cleanup_errors=True) as directory:
        root = Path(directory)
        os.environ["ARMADA_DATA_DIR"] = str(root / "data")
        os.environ["ARMADA_NO_MODEL_SYNC"] = "1"
        os.environ["HOME"] = os.environ["USERPROFILE"] = str(root / "home")
        (root / "home").mkdir()
        realm = build_fixture(root / "realm")
        other = build_fixture(root / "other")
        cfg_path = Path(realm) / "agents/captain/agent.json"
        cfg = util.read_json_state(cfg_path)
        cfg["color"] = "#bf6138"
        util.write_json_atomic(cfg_path, cfg)

        class Fixture(serve.Handler):
            def _route_get(self):
                if self.path.split("?")[0] == "/probe-main":
                    from armada import reader, webui
                    self._send(200, webui.render_agent(reader.read(self.realm), self.realm, "captain", "threads"))
                elif self.path.split("?")[0] in {"/api/auth-status", "/api/scheduler-status", "/api/update-status",
                                               "/api/proposals-count", "/api/notifications"}:
                    self._json(200, {})
                else:
                    super()._route_get()
        Fixture.realm = realm
        server = serve._Server(("127.0.0.1", 0), Fixture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_port}/"

        def fake_chat(root, agent, thread, message, *, on_event, **kwargs):
            th = Thread(Path(root) / "agents" / agent, thread)
            turn = th.begin_turn(message)
            th.save_progress(turn, "Checking the synthetic figures.", "Checking", [])
            on_event({"kind": "text", "text": "Checking the synthetic figures."})
            started.set()
            release.wait(15)
            answer = "Synthetic result: 125.50. Saved once."
            th.complete_turn(turn, answer)
            on_event({"kind": "render", "html": "<p>" + answer + "</p>"})
            return {"ok": True, "output": answer}

        def wait_for(fn, label, timeout=15):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    value = fn()
                    if value:
                        result["checks"].append(label)
                        return value
                except Exception:
                    pass
                time.sleep(.1)
            raise AssertionError(label)

        def ready(window):
            wait_for(lambda: window.events.loaded.is_set() and window.evaluate_js("!!document.getElementById('mc-turns')"),
                     "authenticated conversation loaded")
            # Background test windows must exercise the same polling as visible windows.
            window.evaluate_js("Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});window.mcThreadSync()")

        def text(window):
            return window.evaluate_js("document.getElementById('mc-turns').textContent")

        def check(label, value):
            if not value:
                raise AssertionError(label)
            result["checks"].append(label)

        def screenshot(window, name):
            from System import Action
            from System.IO import FileStream, FileMode, FileAccess
            from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
            done = threading.Event()
            errors = []
            path = str(output.with_name(name + ".png"))
            def capture():
                try:
                    stream = FileStream(path, FileMode.Create, FileAccess.Write)
                    task = window.native.webview.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, stream)
                    def finish():
                        try:
                            task.GetAwaiter().GetResult()
                            stream.Dispose()
                        except Exception as exc:
                            errors.append(str(exc))
                        done.set()
                    threading.Thread(target=finish, daemon=True).start()
                except Exception as exc:
                    errors.append(str(exc)); done.set()
            window.native.Invoke(Action(capture))
            if not done.wait(10) or errors:
                raise AssertionError("screenshot: " + repr(errors))
            result.setdefault("screenshots", []).append(path)

        main = webview.create_window("Thread test", local_auth.browser_url(url, "/probe-main"), hidden=True,
                                     width=1200, height=800)
        windows.append(main)
        native_create = webview.create_window
        def hidden_create(*args, **kwargs):
            window = native_create(*args, **dict(kwargs, hidden=True))
            windows.append(window)
            # Focus/reuse is verified by the registry; keep automated probes invisible.
            window.show = lambda: None
            window.restore = lambda: None
            return window

        def exercise():
            try:
                ready(main)
                main.evaluate_js("document.querySelector('.mc-thread-popout').click()")
                companion = wait_for(lambda: next(iter(app._thread_windows.values()), None), "sidebar opens native companion")
                ready(companion)
                check("both views show the original transcript", "All hands accounted for." in text(main) and
                      "All hands accounted for." in text(companion))
                check("color crescent is visible", companion.evaluate_js("!!document.querySelector('.mc-ax-portrait .mc-avdisc')"))
                check("native frame shaped", companion.native.Region is not None)
                check("same thread reuses its window", app.open_thread(realm, "captain", "main") and len(app._thread_windows) == 1)
                main.evaluate_js("document.getElementById('mc-msg').value='Synthetic question';mcChat('captain','main')")
                wait_for(started.is_set, "sending invokes the shared transport")
                wait_for(lambda: "Checking the synthetic figures." in text(companion), "companion shows progress started in main")
                wait_for(lambda: companion.evaluate_js("document.getElementById('mc-stop').style.display") != "none",
                         "Stop is available in the observing window")
                release.set()
                wait_for(lambda: "Synthetic result: 125.50." in text(main) and "Synthetic result: 125.50." in text(companion),
                         "both views receive the saved reply")
                companion.evaluate_js("document.getElementById('mc-msg').value='Question from companion';mcChat('captain','main')")
                wait_for(lambda: "Question from companion" in text(main), "main receives a message sent by the companion")
                wait_for(lambda: len(Thread(Path(realm)/"agents/captain")._messages()) == 6, "each send is persisted exactly once")
                # Switch the cockpit admission default while the companion remains bound to A.
                Fixture.realm = other
                companion.evaluate_js("document.getElementById('mc-msg').value='Still in original realm';mcChat('captain','main')")
                wait_for(lambda: len(Thread(Path(realm)/"agents/captain")._messages()) == 8, "companion sends to original realm after switch")
                check("other realm unchanged", len(Thread(Path(other)/"agents/captain")._messages()) == 2)
                Fixture.realm = realm
                companion.evaluate_js("document.getElementById('mc-msg').value='Draft stays here';mcAutosize();mcSyncSend()")
                screenshot(main, "thread-main")
                screenshot(companion, "thread-window")
                companion.resize(400, 500)
                time.sleep(.4)
                companion.evaluate_js("mcScrollBottom()")
                screenshot(companion, "thread-window-narrow")
                companion.evaluate_js("document.documentElement.classList.add('armada-dark')")
                screenshot(companion, "thread-window-dark")
                check("narrow layout has no horizontal page overflow", companion.evaluate_js(
                    "document.documentElement.scrollWidth<=innerWidth"))
                companion.evaluate_js("document.querySelector('[data-thread-close]').click()")
                wait_for(lambda: not app._thread_windows, "close clears only the companion registry")
                check("main remains authenticated after close", main.evaluate_js("!!document.getElementById('mc-turns')"))
                check("closed window reopens", app.open_thread(realm, "captain", "main"))
                reopened = next(iter(app._thread_windows.values()))
                ready(reopened)
                check("reopened view retains all conversation content", "Still in original realm" in text(reopened))
                result["ok"] = True
            except Exception:
                result["error"] = traceback.format_exc()
            finally:
                release.set()
                output.write_text(json.dumps(result, indent=2), encoding="utf-8")
                for window in reversed(windows):
                    try:
                        window.destroy()
                    except Exception:
                        pass

        try:
            with patch.object(app, "_main_window", main), patch.object(app, "_app_url", url), \
                    patch.object(app, "_thread_windows", {}), patch.object(app, "_quitting", False), \
                    patch.object(webview, "create_window", hidden_create), patch.object(runner, "chat_stream", fake_chat), \
                    patch.object(Fixture, "_autoname_thread", return_value=None):
                webview.start(exercise, gui="edgechromium", **app._webview_options())
        finally:
            server.shutdown()
            server.server_close()
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    raise SystemExit(run(args.output))
