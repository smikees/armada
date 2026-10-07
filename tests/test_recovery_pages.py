"""Real HTTP document failures are useful and traceable; APIs retain their contracts."""
import http.client
import json
import logging
import re
import threading

import pytest

from armada import local_auth, serve
from armada.webui.recovery import page


@pytest.fixture
def server(tmp_path, monkeypatch):
    class Handler(serve.Handler):
        realm = str(tmp_path/'realm')
        def _get_settings(self):
            raise RuntimeError('PRIVATE EXCEPTION DETAILS')
        def _get_index(self):
            self._send(200, '<html><head></head><body>Home</body></html>')
    httpd = serve._Server(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=httpd.serve_forever, daemon=True)
    worker.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()
    worker.join(timeout=2)


def get(server, path, *, authenticated=True, document=True):
    headers = local_auth.headers(server.server_port) if authenticated else {}
    if document:
        headers.update({'Sec-Fetch-Dest': 'document', 'Accept': 'text/html'})
    conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
    try:
        conn.request('GET', path, headers=headers)
        resp = conn.getresponse()
        return resp.status, dict(resp.getheaders()), resp.read().decode()
    finally:
        conn.close()


@pytest.mark.parametrize('status,path,auth', [
    (500, '/settings?secret=do-not-log', True),
    (409, '/settings?_realm=stale&secret=do-not-log', True),
    (401, '/settings?secret=do-not-log', False),
])
def test_document_failure_has_recovery_and_correlated_log(server, caplog, status, path, auth):
    with caplog.at_level(logging.WARNING, logger='armada.serve'):
        code, headers, body = get(server, path, authenticated=auth)
    assert code == status and headers['Content-Type'].startswith('text/html')
    assert f'data-armada-recovery="{status}"' in body
    assert 'Try again' in body and 'href="/">Return to ARMADA' in body
    reference = re.search(r'Diagnostic reference: <code>([a-f0-9]{12})</code>', body)[1]
    records = [r for r in caplog.records if reference in r.getMessage()]
    assert len(records) == 1
    assert bool(records[0].exc_info) == (status == 500)
    assert 'do-not-log' not in caplog.text
    assert 'PRIVATE EXCEPTION' not in body
    assert server.auth.token not in body
    assert 'armada-realm' not in body  # the Home link must not reattach the stale realm
    assert headers['Cache-Control'].startswith('no-store')
    assert get(server, '/')[0] == 200


@pytest.mark.parametrize('document', [True, False])
def test_api_errors_remain_json_even_with_html_accept(server, document):
    code, headers, body = get(server, '/api/realms', authenticated=False, document=document)
    assert code == 401 and headers['Content-Type'].startswith('application/json')
    assert json.loads(body)['ok'] is False
    code, headers, body = get(server, '/api/realms?_realm=stale', document=document)
    assert code == 409 and json.loads(body)['code'] == 'realm_mismatch'


def test_recovery_renderer_escapes_inputs():
    html = page(409, '<script>reference</script>', '<img src=x onerror=alert(1)>')
    assert '<script>' not in html and '<img' not in html
    assert '&lt;script&gt;' in html and '&lt;img' in html
