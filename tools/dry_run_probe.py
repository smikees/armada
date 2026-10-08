"""Hidden Windows WebView2 Jobs/inspector check using a synthetic realm and engine only."""
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


def run(output, width=1280):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import webview
    from armada import app, dry_runs, inspection, local_auth, models, serve, util
    from armada.engine.base import EngineAdapter, RunResult, Usage
    from armada.engine.contracts import ProviderCapabilities
    from tests.golden_support import build_fixture
    result = {"ok": False, "checks": [], "screenshots": []}
    release = threading.Event()
    with tempfile.TemporaryDirectory(prefix="armada-draft-ui-", ignore_cleanup_errors=True) as directory:
        root = Path(directory).resolve()
        assert root.parent == Path(tempfile.gettempdir()).resolve()
        os.environ["ARMADA_DATA_DIR"] = str(root / "data")
        os.environ["ARMADA_NO_MODEL_SYNC"] = "1"
        os.environ["ARMADA_NOTIFY_MUTE"] = "1"
        os.environ["HOME"] = os.environ["USERPROFILE"] = str(root / "home")
        (root / "home").mkdir()
        realm = Path(build_fixture(root / "realm"))
        from armada import skills
        from armada.model import Skill
        skills.save(realm, 'captain', [Skill(id='review')])
        skill = realm / 'agents/captain/skills/review'
        skill.mkdir(parents=True)
        (skill / 'SKILL.md').write_text('Synthetic test reviewer.')
        (skill / 'test.py').write_text('print("synthetic draft 12.34")')
        (realm / 'input.json').write_text('{"amount":"12.34"}')
        jp = realm / "agents/captain/jobs/synthetic-model-test.json"
        jp.parent.mkdir(parents=True, exist_ok=True)
        job = {"id": jp.stem, "name": "Synthetic model test", "schedule": "manual"}
        job.update(kind="agent", prompt="Produce a synthetic report.", enabled=False)
        job.pop("run", None)
        job.pop("command", None)
        util.write_json_atomic(jp, job)
        job_before = jp.read_bytes()

        class Fixture(serve.Handler):
            capture_html = ""
            def _route_get(self):
                if self.path.split("?")[0] == "/probe-screenshot":
                    self._send(200, type(self).capture_html.encode("utf-8"))
                elif self.path.split("?")[0] in {"/api/auth-status", "/api/scheduler-status", "/api/update-status",
                                               "/api/proposals-count", "/api/notifications", "/api/providers"}:
                    self._json(200, {"ok": True, "logged_in": True})
                else:
                    super()._route_get()
        Fixture.realm = realm
        server = serve._Server(("127.0.0.1", 0), Fixture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_port}/"
        window = webview.create_window("Synthetic dry-run check", local_auth.browser_url(url, "/jobs"),
                                      hidden=True, width=width, height=900)

        class Engine(EngineAdapter):
            name = "mock"
            capabilities = ProviderCapabilities(streaming=True)
            def doctor(self):
                return True, "Synthetic engine"
            def run(self, **kwargs):
                return self.run_stream(**kwargs)
            def run_stream(self, *, model, env, on_proc, **kwargs):
                stopped = threading.Event()
                class Process:
                    def kill(self):
                        stopped.set()
                on_proc(Process())
                report = self.managed_tools.call("write_draft", {"path": "report.md", "content": "Synthetic draft: **12.34**"})
                deadline = time.monotonic() + 30
                while not release.is_set() and not stopped.is_set() and time.monotonic() < deadline:
                    stopped.wait(.05)
                if stopped.is_set():
                    return RunResult(ok=False, cancelled=True, error="Synthetic dry run stopped.")
                data = {"schema_version": 1, "run_id": env["ARMADA_RUN_ID"], "execution": "completed",
                    "audit_outcome": "clear", "delivery": [], "evidence": {"outputs": [{"path": report["path"], "required": True}],
                    "findings": [], "missing_inputs": [], "operational_errors": [], "risk_gates": []}}
                return RunResult(ok=True, model=model, usage=Usage(input=12, output=8),
                    output="Synthetic draft: **12.34**\n<armada_job_result>" + json.dumps(data) + "</armada_job_result>")

        def check(label, fn, timeout=15):
            until = time.monotonic()+timeout
            while time.monotonic() < until:
                try:
                    if fn():
                        result["checks"].append(label)
                        return
                except Exception:
                    pass
                time.sleep(.1)
            raise AssertionError(label)

        def js(code):
            return window.evaluate_js(code)

        def screenshot(name, focus='.mc-dry-runs'):
            # Occluded WebView2 CapturePreview can wait forever for a compositor frame.
            # Behavior is tested in native WebView2; render its actual DOM in an isolated
            # headless Chromium profile for repeatable visual evidence.
            import subprocess
            chrome = Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe"
            if not chrome.exists():
                result.setdefault("notes", []).append("Chrome unavailable; native behavior checked without screenshots.")
                return
            Fixture.capture_html = js("""(() => {
                const copy=document.documentElement.cloneNode(true);
                copy.querySelectorAll('script').forEach(s=>s.remove());
                document.querySelectorAll('select').forEach((s,i)=>{
                    const target=copy.querySelectorAll('select')[i];
                    [...target.options].forEach((o,n)=>o.toggleAttribute('selected',n===s.selectedIndex));
                });
                return '<!doctype html>'+copy.outerHTML;
            })()""") + "<script>addEventListener('load',()=>document.querySelector("+json.dumps(focus)+").scrollIntoView({block:'center'}))</script>"
            path = output.with_name(name + ".png").resolve()
            subprocess.run([str(chrome), "--headless=new", "--disable-gpu", "--no-first-run",
                "--disable-background-networking", "--disable-component-update", "--no-proxy-server",
                "--user-data-dir=" + str(root / ("chrome-" + name)), "--virtual-time-budget=1500",
                "--window-size=" + str(width) + ",900", "--screenshot=" + str(path),
                local_auth.browser_url(url, "/probe-screenshot")], check=True, timeout=30,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            assert path.is_file() and path.stat().st_size > 1000
            result["screenshots"].append(str(path))
            result["screenshot_renderer"] = "Headless Chromium rendering the native WebView2 DOM"

        selector = f'.mc-job[data-owner="captain"][data-jid="{jp.stem}"]'
        panel = selector + ' .mc-dry-runs'
        def exercise():
            try:
                check("Jobs loads the dry-run controls", lambda: js("typeof mcDryStart==='function'"))
                js(f"document.querySelector({json.dumps(selector)}).open=true;document.querySelector({json.dumps(panel+' > summary')}).click()")
                check("Dry run disclosure matches Jobs styling and has one launch control", lambda: js(f"""(() => {{
                    const job=document.querySelector({json.dumps(selector)}), panel=job.querySelector('.mc-dry-runs');
                    const regular=job.querySelector('.mc-job-output-pane > summary'), dry=panel.querySelector(':scope > summary');
                    const a=getComputedStyle(regular), b=getComputedStyle(dry);
                    const picker=job.querySelector('.mc-job-output-pane .mc-job-run-select'), model=panel.querySelector('.mc-dry-model');
                    return panel.open && dry.textContent==='Dry run history' && dry.querySelector('svg').outerHTML===regular.querySelector('svg').outerHTML
                        && ['fontFamily','fontSize','fontWeight','paddingLeft','gap'].every(k=>a[k]===b[k])
                        && Math.abs(dry.getBoundingClientRect().left-regular.getBoundingClientRect().left)<1
                        && getComputedStyle(picker).fontSize===getComputedStyle(model).fontSize
                        && job.querySelectorAll('.mc-dry-start').length===1
                        && ![...job.querySelectorAll('.mc-job-actions button')].some(b=>b.textContent==='Dry run');
                }})()"""))
                check("Dry run is available for a disabled production job", lambda: js(f"!document.querySelector({json.dumps(panel+' .mc-dry-start')}).disabled"))
                check("Available models load", lambda: js(f"document.querySelector({json.dumps(panel+' .mc-dry-model')}).options.length===3"))
                check('Dry run effort uses the shared selector', lambda: js(f"document.querySelector({json.dumps(panel+' .mc-dry-effort')}).classList.contains('mc-job-run-select')"))
                js(f"document.querySelector({json.dumps(panel+' .mc-dry-start')}).click()")
                check("Missing model gives actionable feedback", lambda: "Choose a model" in js(f"document.querySelector({json.dumps(panel+' .mc-dry-message')}).textContent"))
                js(f"document.querySelector({json.dumps(panel+' .mc-dry-model')}).value='gpt-6-luna';document.querySelector({json.dumps(panel+' .mc-dry-start')}).click()")
                check("Started test exposes Stop", lambda: js(f"!document.querySelector({json.dumps(panel+' .mc-dry-stop')}).hidden"))
                first = js(f"document.querySelector({json.dumps(panel)}).dataset.dryRun")
                js(f"document.querySelector({json.dumps(panel+' .mc-dry-stop')}).click()")
                check("Stop reaches the real owned dry-run session", lambda: dry_runs.read(realm, "captain", jp.stem, first)["status"] == "stopped")
                check("Stop returns the controls to idle", lambda: js(f"getComputedStyle(document.querySelector({json.dumps(panel+' .mc-dry-stop')})).display==='none'"))
                release.set()
                js(f"document.querySelector({json.dumps(panel+' .mc-dry-model')}).value='claude-sonnet-5';document.querySelector({json.dumps(panel+' .mc-dry-start')}).click()")
                check("Second model creates independent output", lambda: "Synthetic draft" in js(f"document.querySelector({json.dumps(panel+' .mc-dry-output')}).textContent"))
                second = js(f"document.querySelector({json.dumps(panel)}).dataset.dryRun")
                check("Run IDs differ and production definition is unchanged", lambda: first != second and jp.read_bytes() == job_before)
                js(f"document.querySelector({json.dumps(panel)}).scrollIntoView({{block:'center'}})")
                screenshot("dry-run-jobs-light" if width > 800 else "dry-run-jobs-light-narrow")
                js("document.documentElement.classList.add('armada-dark')")
                screenshot("dry-run-jobs-dark" if width > 800 else "dry-run-jobs-dark-narrow")
                js(f"document.querySelector({json.dumps(panel+' .mc-dry-history')}).value={json.dumps(first)};mcDrySelect(document.querySelector({json.dumps(panel+' .mc-dry-history')}))")
                check("Historical stopped result remains selected", lambda: "Stopped" in js(f"document.querySelector({json.dumps(panel+' .mc-dry-output')}).textContent"))
                window.load_url(local_auth.browser_url(url, f"/job/captain/{jp.stem}"))
                check("Job editor includes draft retention and command settings", lambda: js("!!document.getElementById('j-dry-keep') && typeof mcDryStart==='function'"))
                js("document.querySelector('.mc-dry-runs').open=true")
                check("Reopening a page retains the completed history", lambda: "Synthetic draft" in js("document.querySelector('.mc-dry-output').textContent"))
                check("Draft controls do not overflow", lambda: js("document.querySelector('.mc-dry-runs').scrollWidth <= document.querySelector('.mc-dry-runs').clientWidth+1"))
                window.load_url(local_auth.browser_url(url, "/agent/captain/configure"))
                check("Agent Advanced contains Is inspector", lambda: js("!!document.getElementById('c-inspector')"))
                js("document.getElementById('c-inspector').checked=true;mcSaveAgent('captain')")
                check("Saving inspector grants machine-local authority", lambda: inspection.enabled(realm, "captain"))
                window.load_url(local_auth.browser_url(url, f'/job/captain/{jp.stem}'))
                check('Job editor includes scoped inspector and approved script settings', lambda: js("!!document.getElementById('j-inspector') && !!document.getElementById('j-dry-scripts') && !!document.getElementById('j-dry-approve')"))
                js("document.getElementById('j-inspector').checked=true;document.getElementById('j-dry-scripts').value='review/test.py';document.getElementById('j-dry-approve').checked=true;mcSaveJob('captain','synthetic-model-test')")
                check('Owner save records inspector scope and the script fingerprint', lambda: (lambda j:
                    j.get('inspector') is True and inspection.appconfig.get('dry_run_scripts', {}).get(
                        inspection.identity(realm, 'captain')+'|'+jp.stem) is not None)(util.read_json_state(jp)))
                check('Script approval checkbox resets after saving', lambda: js("!document.getElementById('j-dry-approve').checked"))
                js("document.getElementById('j-dry-scripts').closest('details').open=true")
                check('Script settings fit their section', lambda: js("document.getElementById('j-dry-scripts').scrollWidth<=document.getElementById('j-dry-scripts').clientWidth+1"))
                screenshot('dry-review-editor' if width > 800 else 'dry-review-editor-narrow', '#j-dry-scripts')
                result["ok"] = True
            except Exception:
                result["error"] = traceback.format_exc()
            finally:
                release.set()
                output.write_text(json.dumps(result, indent=2), encoding="utf-8")
                window.destroy()
        try:
            with patch.object(models, "options", return_value=[("gpt-6-luna", "OpenAI · Luna"), ("claude-sonnet-5", "Anthropic · Sonnet")]), \
                    patch("armada.engine.get_engine", return_value=Engine()):
                webview.start(exercise, gui="edgechromium", **app._webview_options())
        finally:
            server.shutdown(); server.server_close()
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=1280)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    raise SystemExit(run(args.output, args.width))
