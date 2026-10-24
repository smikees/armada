r"""Run the opt-in Codex voice POC in a synthetic ARMADA realm, never the owner's realm.

  .venv\Scripts\python tools/voice_preview.py --window
  .venv-codex\Scripts\python tools/voice_preview.py --port 8798

Codex supplies sign-in and WebRTC signaling. No microphone opens until Dictate or Voice chat is clicked.
The printed launch-file path is local/private; no authentication token is printed.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8798)
    parser.add_argument('--window', action='store_true')
    parser.add_argument('--state', default='build/voice-poc/preview.json')
    args = parser.parse_args()
    root = ROOT/os.environ.get('ARMADA_VOICE_LAB', 'build/voice-poc')/'realm'
    os.environ['ARMADA_DATA_DIR'] = str(root.parent/'app-data')
    os.environ['ARMADA_NO_MODEL_SYNC'] = '1'
    os.environ['ARMADA_NO_EXTERNAL_NOTIFY'] = '1'
    from armada import reader, serve, util, webui
    from armada.threads import Thread
    util.write_json_atomic(root/'realm.json', {'name':'Voice Lab — POC', 'default_model':'codex:default',
        'providers':['codex'], 'default_engine':'codex', 'workspace':str(root)})
    agent = root/'agents/voice'
    util.write_json_atomic(agent/'agent.json', {'id':'voice', 'display':'Voice POC', 'role':'Conversation test',
        'model':'codex:default', 'allow_tools':False})
    if not (agent/'mandate.md').exists():
        util.write_text_atomic(agent/'mandate.md', 'You are the ARMADA voice proof of concept. Be concise and conversational.\n')
    if not (agent/'threads/main/messages.jsonl').exists():
        Thread(agent).append('Remember that the code word for our voice test is cobalt.', 'The code word is cobalt.')

    class Preview(serve.Handler):
        realm = str(root)
        def _route_get(self):
            path = self.path.split('?')[0]
            if path == '/':
                self._send(200, webui.render_agent(reader.read(root),root,'voice','threads'))
            elif path == '/api/auth-status':
                self._json(200,{'notice_enabled':False})
            elif path in ('/api/update-status','/api/scheduler-status','/api/providers',
                          '/api/usage-limits','/api/notifications','/api/proposals-count'):
                self._json(200,{})
            else:
                super()._route_get()

    httpd = serve._Server(('127.0.0.1', args.port), Preview)
    base = f'http://127.0.0.1:{httpd.server_port}'
    state = {'base':base, 'realm':str(root), 'launch_file':str(httpd.auth.launch_file),'pid':os.getpid()}
    path = ROOT/args.state
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(state,indent=2),encoding='utf-8')
    print(json.dumps(state),flush=True)
    try:
        if args.window:
            import webview
            from armada import app
            threading.Thread(target=httpd.serve_forever,daemon=True).start()
            # Private fragment is consumed by the app's existing authentication bootstrap.
            window = webview.create_window('ARMADA — Audio and thread fixes preview', base+'/auth#'+httpd.auth.token,
                                          width=1120,height=820)
            # Use the same native companion opener as the installed app in this isolated process.
            app._main_window, app._app_url = window, base
            webview.start(gui='edgechromium')
        else:
            httpd.serve_forever(poll_interval=.1)
    finally:
        httpd.server_close()


if __name__ == '__main__':
    main()
