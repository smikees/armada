"""Exercise installed services with synthetic data, only inside the disposable Sandbox."""
import http.cookiejar
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

assert os.environ.get('USERNAME', '').lower() == 'wdagutilityaccount', 'Sandbox only'
assert Path('C:/armada-results').is_dir(), 'Sandbox result mapping required'
from armada import activerealm, local_auth, realm_registry, runner, setup

realm = Path.home()/'Documents/ARMADA validation realm'
if sys.argv[1] == 'create':
    setup.scaffold(realm, 'scratch', 'Sandbox validation', agents=[{'id':'tester','display':'Tester'}])
    realm_registry.ensure(str(realm), 'Sandbox validation')
    activerealm.remember(str(realm))
    marker = realm/'first-job.txt'
    job = {'kind':'command', 'run':[sys.executable, '-c',
        'from pathlib import Path;Path("first-job.txt").write_text("completed");print("first job completed")']}
    result = runner._run_command(realm, 'tester', 'first-job', job, realm/'agents/tester')
    assert result['status'] == 'ok', result
    assert marker.read_text() == 'completed'
    print('PASS  Installed command job completed and persisted its result')

    # Exercise the browser's bootstrap exchange, including its HttpOnly session cookie.
    token = json.loads((Path.home()/'.armada/local-auth/8756.json').read_text())['token']
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    request = urllib.request.Request('http://127.0.0.1:8756/auth',
        data=b'', headers={'Authorization':'Bearer '+token})
    with opener.open(request, timeout=5) as response: assert response.status == 204
    with opener.open('http://127.0.0.1:8756/api/instance', timeout=5) as response: assert response.status == 200
    print('PASS  Browser bootstrap grants an authenticated session')
    request = urllib.request.Request('http://127.0.0.1:8756/restart', data=b'',
        headers={'Authorization':'Bearer '+token})
    with urllib.request.urlopen(request, timeout=5) as response: assert response.status == 200
    for attempt in range(60):
        time.sleep(1)
        try:
            fresh = local_auth.headers(8756)
            assert fresh and fresh['Authorization'] != 'Bearer '+token
            request = urllib.request.Request('http://127.0.0.1:8756/', headers=fresh)
            with urllib.request.urlopen(request, timeout=3) as response:
                assert 'Sandbox validation' in response.read().decode()
            break
        except Exception:
            if attempt == 59: raise
    print('PASS  Authenticated native restart reopened the realm with a new session credential')
else:
    assert (realm/'first-job.txt').read_text() == 'completed'
    assert any(Path(r['path']) == realm for r in realm_registry.load())
    for attempt in range(60):
        try:
            request = urllib.request.Request('http://127.0.0.1:8756/', headers=local_auth.headers(8756))
            with urllib.request.urlopen(request, timeout=3) as response:
                assert 'Sandbox validation' in response.read().decode()
            break
        except Exception:
            if attempt == 59: raise
            time.sleep(1)
    print('PASS  Reinstalled native app reopened the existing realm and preserved the first job')
