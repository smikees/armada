"""Synthetic native review journey: compact proposals, readable diffs and cadence."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run(output):
    import webview
    from armada import app, appconfig, local_auth, run_policy, serve, util, vtheme
    from tests.golden_support import build_fixture, fixture_inputs
    result = {'ok': False, 'checks': [], 'screenshots': []}
    output = output.resolve()
    with tempfile.TemporaryDirectory(prefix='armada-proposal-ui-', ignore_cleanup_errors=True) as folder, fixture_inputs():
        home = Path(folder)
        (home/'home').mkdir()
        os.environ.update(HOME=str(home/'home'), USERPROFILE=str(home/'home'),
                          ARMADA_DATA_DIR=str(home/'data'), ARMADA_NO_MODEL_SYNC='1', ARMADA_NO_EXTERNAL_NOTIFY='1')
        appconfig.save(vtheme.preferences('armada-ii'))
        root = Path(build_fixture(home/'realm'))
        common = ('\n\n## Completion checks\n\n- Save **one report** with the source date.\n'
                  '- Keep the original files unchanged.\n- Return a short summary with links to the output.\n')
        prompt = ('## Daily checks\n\nRead **five** local reports and flag missing results.\n'
                  'Keep the summary concise.\n\n1. Read `reports/status.json`.\n'
                  '2. Compare the latest results with yesterday.\n3. List exceptions for review.\n'
                  + common * 12)
        saved = {'id': 'review-ui', 'name': 'Daily operations review', 'kind': 'agent',
                 'prompt': prompt, 'allow_tools': True, 'cron': '*/15 15-16 * * 1-5', 'enabled': False}
        path = root/'agents/captain/jobs/review-ui.json'
        pending = path.parent/'_pending/review-ui.json'
        util.write_json_atomic(path, saved)
        run_policy.seal_job(root, 'captain', saved)
        proposed = {**saved, 'prompt': prompt.replace('**five**', '**six**').replace(
                    '3. List exceptions for review.', '3. List exceptions for review.\n4. Include the source timestamp.'),
                    'timeout': 600}
        util.write_json_atomic(pending, proposed)

        class Fixture(serve.Handler):
            def _route_get(self):
                route = self.path.split('?')[0]
                if route == '/probe-screenshot':
                    self._send(200, type(self).capture_html)
                elif route in {'/api/auth-status', '/api/scheduler-status', '/api/proposals-count',
                               '/api/notifications', '/api/providers', '/api/update-status', '/api/usage-limits'}:
                    self._json(200, {'ok': True, 'logged_in': True, 'providers': {}})
                else:
                    super()._route_get()
        Fixture.realm = root
        server = serve._Server(('127.0.0.1', 0), Fixture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}'
        window = webview.create_window('Synthetic proposal review', local_auth.browser_url(base, '/jobs'),
                                       hidden=True, width=1440, height=960)
        def js(code):
            return window.evaluate_js(code)
        def check(name, predicate):
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                try:
                    if predicate():
                        result['checks'].append(name)
                        return
                except Exception:
                    pass
                time.sleep(.1)
            raise AssertionError(name)
        def capture(name, width, height):
            Fixture.capture_html = js("""(() => {
                const d=document.documentElement.cloneNode(true),sources=[...document.querySelectorAll('style,link[rel=stylesheet]')];
                d.querySelectorAll('style,link[rel=stylesheet]').forEach((node,i)=>{
                    const sheet=sources[i].sheet;if(!sheet)return;
                    const style=document.createElement('style');
                    style.textContent=[...sheet.cssRules].map(r=>r.cssText).join('\\n');node.replaceWith(style);
                });
                d.querySelectorAll('script').forEach(s=>s.remove());
                return '<!doctype html>'+d.outerHTML;
            })()""")
            image = output.with_name(output.stem + '-' + name + '.png')
            chrome = Path(os.environ.get('PROGRAMFILES', 'C:/Program Files'))/'Google/Chrome/Application/chrome.exe'
            subprocess.run([str(chrome), '--headless=new', '--disable-gpu', '--no-first-run',
                            '--disable-background-networking', '--disable-component-update', '--no-proxy-server',
                            '--user-data-dir='+str(home/('capture-'+name)), '--virtual-time-budget=1500',
                            f'--window-size={width},{height}', '--screenshot='+str(image),
                            local_auth.browser_url(base, '/probe-screenshot')], check=True, timeout=30,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            assert image.is_file()
            result['screenshots'].append(str(image))
        def fit():
            return js("(() => {const p=document.querySelector('.mc-proposals'),b=p.getBoundingClientRect();return p.scrollWidth<=p.clientWidth+1&&[...p.querySelectorAll('button,select,.mc-prop-values')].filter(x=>x.getClientRects().length).every(x=>{const r=x.getBoundingClientRect();return r.left>=b.left&&r.right<=b.right+1;});})()")
        def exercise():
            try:
                check('Proposals load collapsed', lambda: js("!!document.querySelector('.mc-prop')&&!document.querySelector('.mc-prop').open&&typeof mcJobProposal==='function'"))
                check('Collapsed job occupies a compact row', lambda: js("document.querySelector('.mc-prop').getBoundingClientRect().height<100"))
                check('List and proposal cadence are readable', lambda: js("[...document.querySelectorAll('[data-cadence]')].some(e=>e.dataset.cadence==='weekdays every 15 min, 15:00–16:45')&&document.querySelector('.mc-prop-meta').textContent.includes('every 15 min')"))
                capture('collapsed', 1440, 960)
                js("document.querySelector('.mc-prop>summary').click();true")
                check('Disclosure reveals formatted comparison', lambda: js("document.querySelector('.mc-prop').open&&!!document.querySelector('.mc-prop-values strong ins')&&!!document.querySelector('.mc-prop-values ol')"))
                check('Prompt appears only in the comparison', lambda: js("!document.querySelector('.mc-prop-preview')&&document.querySelectorAll('.mc-prop-values').length>=2"))
                check('Long values scroll within a bounded comparison', lambda: js("[...document.querySelectorAll('.mc-prop-values')].some(e=>e.scrollHeight>e.clientHeight&&e.clientHeight<=361)"))
                check('Body and field headings use compact typography', lambda: js("parseFloat(getComputedStyle(document.querySelector('.mc-prop .mc-md')).fontSize)===12&&parseFloat(getComputedStyle(document.querySelector('.mc-prop-field>h4')).fontSize)<=13"))
                check('Desktop comparison columns share the available width', lambda: js("(() => {const c=[...document.querySelectorAll('.mc-prop-values:first-of-type>.mc-prop-value')];return c.length>=2&&Math.abs(c[0].clientWidth-c[1].clientWidth)<=1;})()") and fit())
                js("document.querySelector('.mc-prop-values').focus();true")
                check('Comparison accepts keyboard scrolling focus', lambda: js("document.activeElement.classList.contains('mc-prop-values')"))
                capture('expanded', 1440, 960)
                assert util.read_json_state(path) == saved and run_policy.verify_job(root, 'captain', saved)
                result['checks'].append('Review leaves the saved job and approval intact')
                window.resize(600, 1100)
                js("document.body.classList.add('armada-dark');mcFontSize.preview(19);true")
                check('Narrow scaled dark comparison fits', lambda: fit() and js("parseFloat(getComputedStyle(document.querySelector('.mc-prop .mc-md')).fontSize)>17&&getComputedStyle(document.querySelector('.mc-prop-values')).gridTemplateColumns.split(' ').length===1"))
                capture('narrow-dark', 600, 1100)
                js("document.querySelector('.mc-prop>summary').click();true")
                check('Proposal collapses again without losing focusability', lambda: js("!document.querySelector('.mc-prop').open"))
                js("document.querySelector('.mc-prop>summary').click();document.querySelector('.mc-propapprove').click();true")
                check('Approve saves the reviewed full prompt', lambda: util.read_json_state(path).get('prompt') == proposed['prompt'])
                assert run_policy.verify_job(root, 'captain', util.read_json_state(path)) and not pending.exists()
                result['checks'].append('Approval reseals the job and removes only its pending proposal')
                result['ok'] = True
            except Exception:
                result['error'] = traceback.format_exc()
            finally:
                util.write_json_atomic(output, result)
                window.destroy()
        try:
            webview.start(exercise, gui='edgechromium', **app._webview_options())
        finally:
            server.shutdown()
            server.server_close()
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output))
