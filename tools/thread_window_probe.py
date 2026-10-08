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
    from armada.engine.base import EngineAdapter, RunResult, Usage
    from armada.engine.contracts import ProviderCapabilities
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

        class SyntheticEngine(EngineAdapter):
            """Only the provider boundary is simulated; persistence and Stop are real."""
            name = "mock"
            capabilities = ProviderCapabilities(streaming=True, cancellation=True, tool_denials=True)

            def doctor(self):
                return True, "Synthetic engine"

            def run(self, *args, **kwargs):
                return self.run_stream(*args, **kwargs)

            def run_stream(self, *args, on_event, on_proc, **kwargs):
                cancelled = threading.Event()
                class Process:
                    pid = 0
                    def kill(self):
                        cancelled.set()
                    def poll(self):
                        return -1 if cancelled.is_set() else None
                on_proc(Process())
                on_event({"kind": "thinking", "text": "Checking synthetic data"})
                on_event({"kind": "tool", "id": "fixture-tool", "name": "Read", "input": {"file": "synthetic.txt"}})
                on_event({"kind": "tool_result", "id": "fixture-tool", "content": "125.50", "is_error": False})
                on_event({"kind": "text", "text": "Checking the synthetic figures."})
                started.set()
                deadline = time.monotonic() + 60
                while not release.is_set() and not cancelled.is_set() and time.monotonic() < deadline:
                    cancelled.wait(.05)
                if cancelled.is_set():
                    return RunResult(ok=False, cancelled=True, error="Run stopped by the owner.",
                                     output="Checking the synthetic figures.", usage=Usage(input=10, output=5))
                answer = "Synthetic result: 125.50. Saved once."
                on_event({"kind": "text", "text": "\n\n" + answer})
                return RunResult(ok=True, output=answer, usage=Usage(input=10, output=10))

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
            wait_for(lambda: window.events.loaded.is_set() and window.evaluate_js("!!document.getElementById('mc-turns') && typeof window.mcThreadSync==='function'"),
                     "authenticated conversation loaded")
            # Occluded windows must keep observing too; do not override document.hidden.
            window.evaluate_js("window.mcThreadSync()")

        def text(window):
            return window.evaluate_js("document.getElementById('mc-turns').textContent")

        def transcript(window):
            return window.evaluate_js("document.getElementById('mc-turns').innerHTML")

        def idle(window):
            return window.evaluate_js("!mcGen && !mcCtrl")

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

        def composite(window, name):
            from System import Action
            from System.Drawing import Bitmap, Color, Graphics, SolidBrush
            from System.Drawing.Imaging import ImageFormat
            from System.Drawing.Drawing2D import CombineMode
            shadow = window._thread_shadow
            path = output.with_name(name+".png")
            def draw():
                foreground = Bitmap(str(output.with_name("thread-window.png")))
                canvas = Bitmap(shadow.bitmap.Width,shadow.bitmap.Height)
                graphics = Graphics.FromImage(canvas)
                region = window.native.Region.Clone()
                brush = SolidBrush(window.native.BackColor)
                try:
                    graphics.Clear(Color.FromArgb(204,120,92))
                    pad = round(shadow.PAD*float(window.native._scale))
                    region.Translate(float(pad),float(pad))
                    graphics.SetClip(region,CombineMode.Replace)
                    graphics.FillRegion(brush,region)
                    graphics.DrawImageUnscaled(foreground,pad,pad)
                    graphics.ResetClip()
                    graphics.DrawImageUnscaled(shadow.bitmap,0,0)
                    canvas.Save(str(path),ImageFormat.Png)
                finally:
                    brush.Dispose();region.Dispose();graphics.Dispose();canvas.Dispose();foreground.Dispose()
            window.native.Invoke(Action(draw))
            result.setdefault("screenshots",[]).append(str(path))

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
                main.evaluate_js("document.querySelector('.mc-thdots').click();document.querySelector('.mc-thread-detach').click()")
                companion = wait_for(lambda: next(iter(app._thread_windows.values()), None), "sidebar opens native companion")
                ready(companion)
                check("both views show the original transcript", "All hands accounted for." in text(main) and
                      "All hands accounted for." in text(companion))
                check("color crescent is visible", companion.evaluate_js("!!document.querySelector('.mc-ax-portrait .mc-avdisc')"))
                check("native frame shaped", companion.native.Region is not None)
                from System import Action
                from System.Drawing.Imaging import ImageFormat
                shadow = wait_for(lambda: getattr(companion, "_thread_shadow", None), "native shadow attached")
                check("native shadow owns an alpha window", bool(shadow.handle and shadow.bitmap))
                shadow_path = str(output.with_name("thread-native-shadow.png"))
                companion.native.Invoke(Action(lambda: shadow.bitmap.Save(shadow_path, ImageFormat.Png)))
                check("native shadow has transparent conversation centre", shadow.bitmap.GetPixel(
                    shadow.bitmap.Width//2, shadow.bitmap.Height//2).A == 0)
                check("native shadow has soft pixels below the panel", 0 < shadow.bitmap.GetPixel(
                    shadow.bitmap.Width//2, shadow.bitmap.Height-round((shadow.PAD+3)*float(companion.native._scale))).A < 100)
                scale = float(companion.native._scale)
                # The supplied reference provides a useful numeric guard against a hard edge or clear seam.
                panel_right = shadow.bitmap.Width-round((shadow.PAD+8)*scale)
                panel_bottom = shadow.bitmap.Height-round((shadow.PAD+8)*scale)
                side_y = shadow.bitmap.Height//2
                centre_x = shadow.bitmap.Width//2
                side_alpha = [shadow.bitmap.GetPixel(panel_right+round(d*scale), side_y).A/255
                              for d in (1,8,16,32,48)]
                bottom_alpha = [shadow.bitmap.GetPixel(centre_x,panel_bottom+round(d*scale)).A/255
                                for d in (1,8,16,32,48,60)]
                result["shadow_alpha"] = {"right":side_alpha,"bottom":bottom_alpha}
                check("shadow meets the frame without a clear seam", side_alpha[0] > .12)
                check("shadow follows reference side falloff", all(abs(a-b)<.045 for a,b in
                    zip(side_alpha,(.167,.108,.059,.01,0))))
                check("shadow follows reference bottom falloff", all(abs(a-b)<.045 for a,b in
                    zip(bottom_alpha,(.304,.265,.220,.127,.054,.025))))
                check("detached frame has no border", companion.evaluate_js(
                    "getComputedStyle(document.querySelector('.mc-ax-panel')).borderRightWidth==='0px'"))
                check("avatar protrudes only sixteen pixels above header", companion.evaluate_js(
                    "Math.abs(document.querySelector('.mc-chat-heading').getBoundingClientRect().top-document.querySelector('.mc-ax-portrait').getBoundingClientRect().top-16)<1"))
                check("close control has equal top and right insets", companion.evaluate_js(
                    "(()=>{const p=document.querySelector('.mc-ax-panel').getBoundingClientRect(),x=document.querySelector('[data-thread-close]').getBoundingClientRect();return Math.abs((p.right-x.right)-(x.top-p.top))<1})()"))
                check("detached status dot is smaller", companion.evaluate_js(
                    "getComputedStyle(document.querySelector('.mc-ax-portrait .mc-actdot')).width==='14px'"))
                check("avatar and header have subtle elevation", companion.evaluate_js(
                    "['.mc-ax-portrait','.mc-chat-heading'].every(s=>getComputedStyle(document.querySelector(s)).boxShadow!=='none')"))
                check("resize grip available", companion.evaluate_js(
                    "!document.querySelector('[data-thread-resize]').hidden"))
                # Exercise the real Windows sizing loop without moving the user's cursor.
                import ctypes
                sizing = threading.Event()
                def resize_began(*_):
                    sizing.set()
                companion.native.ResizeBegin += resize_began
                companion.evaluate_js("document.querySelector('[data-thread-resize]').dispatchEvent(new PointerEvent('pointerdown',{button:0,bubbles:true}))")
                entered = sizing.wait(3)
                user, _ = __import__("armada.thread_frame", fromlist=["_api"])._api()
                from ctypes import wintypes
                user.PostMessageW.argtypes = [wintypes.HWND,wintypes.UINT,ctypes.c_size_t,ctypes.c_ssize_t]
                hwnd = int(companion.native.Handle.ToInt64())
                user.PostMessageW(hwnd, 0x001F, 0, 0)  # WM_CANCELMODE leaves the sizing loop.
                user.PostMessageW(hwnd, 0x0202, 0, 0)  # WM_LBUTTONUP, no cursor manipulation.
                check("drag grip enters Windows sizing loop", entered)
                companion.native.ResizeBegin -= resize_began
                before_width = companion.width
                companion.evaluate_js("document.querySelector('[data-thread-resize]').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}))")
                wait_for(lambda: companion.width == before_width+20, "resize grip changes native width")
                wait_for(lambda: shadow.size[0] == companion.native.ClientSize.Width, "shadow follows native resize")
                check("compact header includes thread title beside the portrait", companion.evaluate_js(
                    "document.getElementById('mc-cttitle').getBoundingClientRect().top < 105 && document.querySelector('.mc-thread-identity').textContent.includes('Captain')"))
                check("detached messages have no avatar columns", companion.evaluate_js(
                    "Array.from(document.querySelectorAll('#mc-turns>.mc-turn:not([data-role=event])>div:first-child>div:first-child')).every(e=>getComputedStyle(e).display==='none')"))
                check("owner attribution is retained as text", companion.evaluate_js(
                    "getComputedStyle(document.querySelector('#mc-turns>.mc-turn[data-role=user]>div:first-child>div:last-child'),'::before').content.length>2"))
                check("main view keeps its avatar columns", main.evaluate_js(
                    "getComputedStyle(document.querySelector('#mc-turns>.mc-turn[data-role=assistant]>div:first-child>div:first-child')).display!=='none'"))
                check("same thread reuses its window", app.open_thread(realm, "captain", "main") and len(app._thread_windows) == 1)
                main.evaluate_js("document.getElementById('mc-msg').value='Synthetic question';mcChat('captain','main')")
                wait_for(started.is_set, "sending invokes the shared transport")
                wait_for(lambda: "Checking the synthetic figures." in text(companion), "companion shows progress started in main")
                wait_for(lambda: companion.evaluate_js("document.getElementById('mc-stop').style.display") != "none",
                         "Stop is available in the observing window")
                wait_for(lambda: "Checking the synthetic figures." in text(main) and transcript(main) == transcript(companion),
                         "sender and occluded companion have identical live HTML and tool activity")
                release.set()
                wait_for(lambda: "Synthetic result: 125.50." in text(main) and "Synthetic result: 125.50." in text(companion),
                         "both views receive the saved reply")
                wait_for(lambda: idle(main) and idle(companion) and transcript(main) == transcript(companion),
                         "both views have identical terminal HTML")
                companion.evaluate_js("document.getElementById('mc-msg').value='Question from companion';mcChat('captain','main')")
                wait_for(lambda: "Question from companion" in text(main), "main receives a message sent by the companion")
                wait_for(lambda: len(Thread(Path(realm)/"agents/captain")._messages()) == 6, "each send is persisted exactly once")
                wait_for(lambda: idle(companion), "companion finishes its sending transport")
                # Switch the cockpit admission default while the companion remains bound to A.
                Fixture.realm = other
                companion.evaluate_js("document.getElementById('mc-msg').value='Still in original realm';mcChat('captain','main')")
                wait_for(lambda: len(Thread(Path(realm)/"agents/captain")._messages()) == 8, "companion sends to original realm after switch")
                check("other realm unchanged", len(Thread(Path(other)/"agents/captain")._messages()) == 2)
                Fixture.realm = realm
                # The old cockpit page deliberately refuses requests after a realm
                # switch. Reload its bound page before comparing the original realm.
                main.load_url(local_auth.browser_url(url, "/probe-main"))
                ready(main)
                wait_for(lambda: idle(main) and idle(companion), "both views idle after realm-bound send")
                for sender, stopper, label in ((main, companion, "observing detached window"),
                                                (companion, companion, "sending detached window"),
                                                (companion, main, "observing main window")):
                    release.clear();started.clear()
                    sender.evaluate_js("document.getElementById('mc-msg').value='Cancel from " + label + "';mcChat('captain','main')")
                    wait_for(started.is_set, "live turn starts for cancellation from " + label)
                    wait_for(lambda: stopper.evaluate_js("mcGen") and "Checking the synthetic figures." in text(stopper),
                             "Stop observes the active conversation in " + label)
                    wait_for(lambda: transcript(main) == transcript(companion), "live snapshots match before Stop in " + label)
                    stopper.evaluate_js("mcTid='deliberately-stale-id';document.getElementById('mc-stop').click()")
                    wait_for(lambda: idle(main) and idle(companion), "Stop actually cancels the backend from " + label)
                    wait_for(lambda: transcript(main) == transcript(companion), "cancelled snapshots match from " + label)
                    check("cancelled turn persisted once from " + label,
                          Thread(Path(realm)/"agents/captain")._messages()[-1].get("status") == "stopped")
                release.clear();started.clear()
                main.evaluate_js("document.getElementById('mc-msg').value='Continue after disconnect';mcChat('captain','main')")
                wait_for(started.is_set, "turn admitted before observer disconnect")
                main.evaluate_js("mcCtrl.abort()")
                wait_for(lambda: main.evaluate_js("!mcCtrl && mcGen && document.getElementById('mc-msg').disabled"),
                         "interrupted transport retains the backend busy state")
                release.set()
                wait_for(lambda: idle(main) and idle(companion) and transcript(main) == transcript(companion),
                         "interrupted sender and companion reconcile the durable completion")
                companion.evaluate_js("document.getElementById('mc-msg').value='Draft stays here';mcAutosize();mcSyncSend()")
                screenshot(main, "thread-main")
                screenshot(companion, "thread-window")
                composite(companion, "thread-window-orange")
                companion.resize(400, 500)
                time.sleep(.4)
                companion.evaluate_js("mcScrollBottom()")
                screenshot(companion, "thread-window-narrow")
                companion.evaluate_js("document.documentElement.classList.add('armada-dark')")
                screenshot(companion, "thread-window-dark")
                # Long labels must ellipsize without covering Close or creating overflow.
                companion.evaluate_js("document.querySelector('.mc-ax-name').textContent='A very long synthetic agent name';document.querySelector('.mc-ax-subtitle').textContent='A very long realm name';document.getElementById('mc-cttitle').textContent='A very long thread name for responsive verification'")
                check("long header labels stay inside the panel", companion.evaluate_js(
                    "document.documentElement.scrollWidth<=innerWidth && document.querySelector('[data-thread-close]').getBoundingClientRect().right<innerWidth"))

                check("narrow layout has no horizontal page overflow", companion.evaluate_js(
                    "document.documentElement.scrollWidth<=innerWidth"))
                companion.evaluate_js("document.querySelector('[data-thread-close]').click()")
                wait_for(lambda: not app._thread_windows, "close clears only the companion registry")
                check("native shadow closes with its thread", shadow.handle is None and shadow.bitmap is None)
                check("main remains authenticated after close", main.evaluate_js("!!document.getElementById('mc-turns')"))
                check("closed window reopens", app.open_thread(realm, "captain", "main"))
                reopened = next(iter(app._thread_windows.values()))
                ready(reopened)
                check("reopened view retains all conversation content", "Still in original realm" in text(reopened))
                release.clear();started.clear()
                reopened.evaluate_js("document.getElementById('mc-msg').value='Close while running';mcChat('captain','main')")
                wait_for(started.is_set, "reopened companion starts a real coordinated turn")
                reopened.evaluate_js("document.querySelector('[data-thread-close]').click()")
                wait_for(lambda: not app._thread_windows, "sending companion closes during its active turn")
                check("closing its observer does not stop the conversation", main.evaluate_js("mcGen") or bool(
                    __import__('armada.execution', fromlist=['ACTIVE_RUNS']).ACTIVE_RUNS))
                check("active conversation can be reopened", app.open_thread(realm, "captain", "main"))
                reopened = next(iter(app._thread_windows.values()))
                ready(reopened)
                wait_for(lambda: reopened.evaluate_js("mcGen") and transcript(reopened) == transcript(main),
                         "reopened active conversation has identical live content and Stop")
                reopened.evaluate_js("document.getElementById('mc-stop').click()")
                wait_for(lambda: idle(main) and idle(reopened) and transcript(main) == transcript(reopened),
                         "reopened observer can Stop and reconcile the active turn")
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
                    patch.object(webview, "create_window", hidden_create), patch.object(runner, "_select_engine", return_value=SyntheticEngine()), \
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
