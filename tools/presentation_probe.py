"""Real hidden renderer/browser fault injection against an isolated synthetic desktop.

Reuses startup's owner/auth/tray harness. Never targets another app's browser process.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import threading
import time


def exercise(window, result, wait_for, before, effects, finish_effect):
    from System import Action
    from System.Diagnostics import Process
    from armada import app, instance, local_auth, util
    guard = window.native._armada_presentation
    hwnd = window.native.Handle.ToInt64()
    headers = local_auth.headers(before['port'])

    def on_ui(fn):
        done, values, errors = threading.Event(), [], []
        def apply():
            try: values.append(fn())
            except Exception as exc: errors.append(exc)
            finally: done.set()
        window.native.BeginInvoke(Action(apply))
        assert done.wait(3), 'native UI callback stalled'
        if errors: raise errors[0]
        return values[0] if values else None

    def restored(previous, old, label):
        wait_for(lambda: guard.recoveries > previous and guard.state == 'healthy', label, timeout=35)
        assert on_ui(lambda: old.IsDisposed)
        assert on_ui(lambda: window.native.Handle.ToInt64()) == hwnd
        count = on_ui(lambda: sum('WebView2' in str(c.GetType()) for c in window.native.Controls))
        assert count == 1, 'an old browser control remained attached'
        current = instance.current()
        assert (current['pid'], current['port'], current['nonce']) == (before['pid'], before['port'], before['nonce'])
        assert local_auth.headers(before['port']) == headers
        assert app._browser_result(window, 'document.getElementById("mc-msg").value', timeout=2) == 'unsent draft'
        assert app._browser_result(window, 'location.pathname+location.search', timeout=2) == '/?_realm=none'
        result['checks'].append(label + ': old control disposed; same HWND/server/auth; draft and realm preserved')

    # Freeze a synthetic side effect in a server worker, then lose its client.
    wait_for(lambda: guard.route == '/?_realm=none', 'recovery remembers the displayed realm')
    app._browser_result(window, "fetch('/api/probe-effect',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).catch(()=>{});true")
    wait_for(lambda: effects['started'] == 1, 'one synthetic request accepted')
    old, previous = on_ui(lambda: guard.backend.webview), guard.recoveries
    on_ui(lambda: guard.backend.webview.CoreWebView2.CallDevToolsProtocolMethodAsync('Page.crash', '{}'))
    restored(previous, old, 'renderer crash recovers automatically')
    assert effects == {'started': 1, 'finished': 0}
    finish_effect.set()
    wait_for(lambda: effects['finished'] == 1, 'in-flight work completes after client loss without replay')

    old, previous = on_ui(lambda: guard.backend.webview), guard.recoveries
    app._browser_result(window, "setTimeout(()=>{while(true){}},50);true")
    time.sleep(.15)
    start = time.monotonic()
    try:
        app._browser_result(window, '1+1', timeout=.15)
        raise AssertionError('infinite renderer loop did not stall script execution')
    except OSError:
        assert time.monotonic() - start < 1
    result['checks'].append('native browser call deadline includes stalled renderer')
    on_ui(lambda: None)
    restored(previous, old, 'unresponsive renderer recovers automatically')

    # A browser-process fault affects all controls sharing this isolated profile.
    assert app.open_alexander()
    wait_for(lambda: app._alex_window is not None and getattr(app._alex_window.native, '_armada_presentation', None),
             'companion recovery controller attached')
    companion = app._alex_window
    wait_for(lambda: app._browser_result(companion, "!!document.querySelector('.mc-ax-compose textarea')", timeout=1),
             'companion composer ready')
    app._browser_result(companion, "(()=>{const e=document.querySelector('.mc-ax-compose textarea');e.value='companion draft';e.dispatchEvent(new Event('input'));return true;})()")
    other = companion.native._armada_presentation
    wait_for(lambda: other.drafts.get('alexander', {}).get('value') == 'companion draft',
             'fresh companion draft acknowledged outside the browser process')
    old, previous = on_ui(lambda: guard.backend.webview), guard.recoveries
    def crash_owned_browser():
        folder = Path(str(guard.backend.user_data_folder)).resolve()
        assert folder.is_relative_to(util.data_dir().resolve()), 'probe must own the browser profile'
        process = Process.GetProcessById(int(guard.backend.webview.CoreWebView2.BrowserProcessId))
        assert process.Id != os.getpid() and process.ProcessName.lower() == 'msedgewebview2'
        process.Kill()
    on_ui(crash_owned_browser)
    try:
        wait_for(lambda: guard.state == 'failed', 'automatic recovery budget stops repeated failures')
    except Exception:
        result['browser_failure_state'] = {'main': guard.state, 'companion': other.state,
            'main_recoveries': guard.recoveries, 'companion_recoveries': other.recoveries,
            'quitting': app._quitting, 'timer': on_ui(lambda: guard.timer.Enabled)}
        raise
    assert on_ui(lambda: guard.panel is not None and guard.retry.Enabled)
    def capture_panel(controller=guard, name='main'):
        from System.Drawing import Bitmap, Color, Rectangle
        from System.Drawing.Imaging import ImageFormat
        panel = controller.panel
        original = panel.BackColor, panel.ForeColor
        try:
            for theme in ('light', 'dark'):
                panel.BackColor = Color.White if theme == 'light' else Color.FromArgb(30, 32, 36)
                panel.ForeColor = Color.FromArgb(30, 32, 36) if theme == 'light' else Color.White
                bitmap = Bitmap(panel.Width, panel.Height)
                try:
                    panel.DrawToBitmap(bitmap, Rectangle(0, 0, panel.Width, panel.Height))
                    bitmap.Save(str(Path(__file__).resolve().parents[1]/f'build/m7-recovery-{name}-{theme}.png'), ImageFormat.Png)
                finally:
                    bitmap.Dispose()
        finally:
            panel.BackColor, panel.ForeColor = original
    on_ui(capture_panel)
    on_ui(lambda: guard.retry.PerformClick())
    restored(previous, old, 'owner retry recovers browser process loss')
    wait_for(lambda: other.recoveries == 1 and other.state == 'healthy', 'shared-browser companion recovers independently')
    assert app._browser_result(companion, "document.querySelector('.mc-ax-compose textarea').value", timeout=2) == 'companion draft'
    result['checks'].append('companion draft survives browser-process loss')
    companion.resize(400, 500)
    def preview_companion():
        other.show_panel('The browser view could not be restored. You can try again or close this window.', retry=True)
        capture_panel(other, 'companion')
        other.hide_panel()
    on_ui(preview_companion)
    assert effects == {'started': 1, 'finished': 1}, 'recovery replayed a request'
    assert not guard.calls.calls
    result['checks'].append('repeated recovery retains bounded native operations and never replays work')


def verify(stage):
    """Mandatory packaged M7 gate, alongside normal tray/update teardown checks."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix='armada-presentation-result-') as directory:
        output = Path(directory) / 'result.json'
        completed = subprocess.run([str(stage/'python/python.exe'), str(Path(__file__).resolve()),
            '--output', str(output), '--staged'], cwd=stage, timeout=210,
            creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True, text=True)
        if not output.exists():
            raise RuntimeError('Presentation gate exited without evidence: ' + completed.stderr[-2000:])
        result = json.loads(output.read_text(encoding='utf-8'))
        if completed.returncode or not result.get('ok'):
            raise RuntimeError('Presentation gate failed: ' + result.get('error', completed.stderr[-2000:]))
        evidence = Path(__file__).resolve().parents[1]/'build/presentation-recovery-staged.json'
        evidence.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(f"Native presentation: {len(result['checks'])} recovery/lifecycle checks passed", flush=True)


if __name__ == '__main__':
    import importlib.util
    spec = importlib.util.spec_from_file_location('armada_startup_probe', Path(__file__).with_name('startup_recovery_probe.py'))
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--staged', action='store_true')
    args = parser.parse_args()
    raise SystemExit(harness.run(args.output, tray_lifecycle=True, staged=args.staged,
                         restart_mode='busy', presentation=exercise))
