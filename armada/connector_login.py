"""Bounded connector OAuth attempts; CLI output and authorization URLs stay in memory."""
import atexit
import logging
import re
import threading
import time
from urllib.parse import parse_qs, urlsplit

from .engine.process import supervise

_lock = threading.RLock()
_attempts = {}
_closing = False


def _url(text):
    for value in re.findall(r'https://[^\s\x1b<>"\']+', text):
        try:
            parsed = urlsplit(value)
            query = parse_qs(parsed.query)
            if (parsed.hostname and not parsed.username and not parsed.password
                    and parsed.port in (None, 443) and query.get('client_id')
                    and query.get('response_type') == ['code']):
                return value
        except ValueError:
            continue
    return ''


def _error(text):
    # CLI OAuth errors can contain a state, code, token or authorization URL.
    text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
    text = re.sub(r'https?://\S+', '[URL omitted]', text)
    text = re.sub(r'(?i)\bBearer\s+\S+', 'Bearer [redacted]', text)
    text = re.sub(r'(?i)(client_secret|access_token|refresh_token|authorization|code|state)[\"\']?\s*[=:]\s*\S+',
                  r'\1=[redacted]', text)
    return text.strip()[-1200:]


def state(key):
    with _lock:
        item = _attempts.get(key)
        if not item:
            return {}
        if item.get('finished') and time.monotonic() - item['finished'] > 900:
            del _attempts[key]
            return {}
        return {k: item[k] for k in ('state', 'reason', 'login_url')}


def begin(key, argv, cwd=None, env=None, on_finish=None):
    with _lock:
        if _closing:
            return {'ok': False, 'state': 'failed', 'error': 'ARMADA is shutting down.'}
        if state(key).get('state') in ('starting', 'sign_in'):
            return {'ok': True, **state(key)}
        item = {'state': 'starting', 'reason': 'Preparing connector sign-in…', 'login_url': '',
                'handle': None, 'changed': threading.Event()}
        _attempts[key] = item

    def work():
        def own(handle):
            with _lock:
                item['handle'] = handle
                if _closing:
                    handle.kill()
        def output(line):
            url = _url(line)
            if url:
                with _lock:
                    item.update(state='sign_in', reason='The CLI provided a sign-in page. Open it if your browser did not appear, then recheck.', login_url=url)
                    item['changed'].set()
        try:
            result = supervise(argv, prompt='', on_line=output, timeout=300, cwd=cwd,
                               env=env, on_proc=own)
            error = _error((result.error if result.timed_out or result.cancelled else result.stderr or result.error) or '')
            with _lock:
                if result.error or result.returncode != 0:
                    item.update(state='failed', reason=error or 'Connector sign-in did not complete. Recheck and retry.', login_url='')
                else:
                    item.update(state='configured', reason='Sign-in command finished. Recheck to verify live tools.', login_url='')
        except Exception as exc:
            # OAuth exceptions may contain credentials; log only the exception class.
            logging.getLogger(__name__).warning('Connector sign-in failed (%s)', type(exc).__name__)
            with _lock:
                item.update(state='failed', reason=_error(str(exc)), login_url='')
        finally:
            with _lock:
                item['handle'] = None
                item['finished'] = time.monotonic()
                item['changed'].set()
            if on_finish:
                on_finish()
    threading.Thread(target=work, daemon=True, name='connector-login').start()
    item['changed'].wait(timeout=.5)
    result = state(key)
    return {'ok': result['state'] != 'failed', **result,
            **({'error': result['reason']} if result['state'] == 'failed' else {})}


@atexit.register
def _close():
    global _closing
    with _lock:
        _closing = True
        for item in _attempts.values():
            if item.get('handle'):
                item['handle'].kill()
