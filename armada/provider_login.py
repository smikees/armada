"""Owned browser-login processes. Only validated authorization URLs are held, in memory.

The official CLI owns OAuth and credentials. Output is drained, never logged or persisted.
"""
import atexit
import os
import re
import signal
import subprocess
import threading
import time
import urllib.parse
import webbrowser

_lock = threading.RLock()
_attempts = {}
_HOSTS = {"claude": {"claude.ai", "console.anthropic.com", "platform.claude.com"},
          "codex": {"auth.openai.com"}, "gemini": {"accounts.google.com"}}


def authorization_url(provider, text):
    for url in re.findall(r'https://[^\s\x1b<>"\']+', text):
        url = url.rstrip(').,')
        parsed = urllib.parse.urlsplit(url)
        paths = ('/o/oauth2/v2/auth', '/o/oauth2/auth') if provider == 'gemini' else ('/oauth/authorize', '/authorize')
        if (parsed.hostname in _HOSTS[provider] and not parsed.username and not parsed.password
                and parsed.port in (None, 443) and parsed.path.rstrip('/') in paths):
            return url
    return ''


def state(provider):
    with _lock:
        item = _attempts.get(provider, {})
        # CLIs can print the URL without a newline. Wait for a quiet output buffer rather
        # than blocking in readline, or publishing a URL while it is still being written.
        if item.get('pending') and time.monotonic() - item.get('output_at', 0) >= .25:
            try:
                url = authorization_url(provider, item.get('output', ''))
                if url:
                    item['url'] = url
            except ValueError:
                pass
        url = item.get('url', '') if item.get('pending') else ''
        return {"pending": bool(item.get('pending')), "login_error": item.get('error', ''),
                "can_open_login": bool(url), "login_url": url}


def _stop(item):
    proc = item.get('proc')
    tree = item.pop('tree', None)
    if tree:
        tree.close()
    elif proc and proc.poll() is None:
        if os.name == 'nt':
            proc.kill()
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def cancel(provider):
    with _lock:
        item = _attempts.get(provider)
        if item:
            _stop(item)
            item.update(pending=False, url='', output='', error='')
    return {"ok": True}


def open_page(provider):
    with _lock:
        item = _attempts.get(provider, {})
        url = item.get('url') if item.get('pending') else ''
    if not url or not authorization_url(provider, url):
        return {"ok": False, "error": "The sign-in page is not ready. Try signing in again."}
    return {"ok": bool(webbrowser.open(url, new=2))}


def begin(provider, launcher):
    if provider == 'gemini':
        return _begin_gemini(launcher)
    with _lock:
        if state(provider)['pending']:
            return {"ok": True, "pending": True}
        tree = None
        proc = None
        try:
            if os.name == 'nt':
                from .engine.windows_job import WindowsJob
                tree = WindowsJob()
            args = ['auth', 'login', '--claudeai'] if provider == 'claude' else ['login']
            proc = subprocess.Popen(launcher + args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=0x08000004 if os.name == 'nt' else 0, start_new_session=os.name != 'nt')
            if tree:
                tree.attach_and_resume(proc)
        except OSError:
            if tree:
                tree.close()
            if proc and proc.poll() is None:
                proc.kill()
            return {"ok": False, "error": "Could not start sign-in. Check the CLI installation and retry."}
        item = {'proc': proc, 'tree': tree, 'pending': True, 'url': '', 'error': ''}
        _attempts[provider] = item

    def read():
        while True:
            try:
                chunk = proc.stdout.read1(8192)
            except (OSError, ValueError):
                return  # cancellation may close the pipe while the reader is draining
            if not chunk:
                return
            line = chunk.decode('utf-8', errors='replace')
            with _lock:
                if not item['pending']:
                    continue
                item['output'] = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', (item.get('output', '') + line)[-32768:])
                item['output_at'] = time.monotonic()
                if 'address already in use' in line.lower():
                    item['error'] = 'Another sign-in is using the browser callback. Finish or close it, then retry.'
                elif 'CODEX_HOME' in line and 'does not exist' in line:
                    item['error'] = 'Codex configuration folder is unavailable. Check its location and retry.'

    reader = threading.Thread(target=read, daemon=True, name=f'{provider}-login-output')
    reader.start()
    def watch():
        try:
            code = proc.wait(timeout=600)
            reader.join(timeout=2)
            with _lock:
                if item['pending'] and code:
                    item['error'] = item['error'] or 'Sign-in did not complete. Please try again.'
        except subprocess.TimeoutExpired:
            with _lock:
                item['error'] = 'Sign-in timed out. Please try again.'
        finally:
            with _lock:
                _stop(item)
                item.update(pending=False, url='', output='')
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            reader.join(timeout=2)
            for stream in (proc.stdin, proc.stdout):
                if stream:
                    stream.close()
    threading.Thread(target=watch, daemon=True, name=f'{provider}-login-watch').start()
    return {"ok": True, "pending": True}


@atexit.register
def _close():
    for provider in list(_attempts):
        cancel(provider)


def _begin_gemini(launcher):
    """Google's supported CLI requires one interactive login; headless calls never prompt."""
    import tempfile
    from .engine.gemini import GeminiEngine, invalidate_auth
    with _lock:
        if state('gemini')['pending']:
            return {"ok": True, "pending": True}
        folder = tempfile.TemporaryDirectory(prefix='armada-google-signin-')
        tree = None
        proc = None
        try:
            if os.name == 'nt':
                from .engine.windows_job import WindowsJob
                tree = WindowsJob()
            proc = subprocess.Popen(launcher, cwd=folder.name,
                creationflags=0x00000014 if os.name == 'nt' else 0,
                start_new_session=os.name != 'nt')
            if tree:
                tree.attach_and_resume(proc)
        except OSError:
            if tree: tree.close()
            if proc and proc.poll() is None: proc.kill()
            folder.cleanup()
            return {"ok": False, "error": "Could not open Google's sign-in window. Check the CLI installation."}
        item = {'proc':proc,'tree':tree,'pending':True,'url':'','error':''}
        _attempts['gemini'] = item
    def watch():
        try:
            deadline = time.monotonic()+600
            while proc.poll() is None and item['pending'] and time.monotonic()<deadline:
                time.sleep(3)
                if GeminiEngine().auth_status(force=True).get('logged_in'):
                    invalidate_auth()
                    return
            if item['pending']:
                item['error'] = 'Google sign-in did not complete. Please try again.'
        finally:
            with _lock:
                _stop(item); item.update(pending=False,url='',output='')
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: pass
            finally: folder.cleanup()
    threading.Thread(target=watch,daemon=True,name='gemini-login-watch').start()
    return {"ok":True,"pending":True}
