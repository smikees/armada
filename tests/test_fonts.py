"""Appearance → Fonts (temporary, v0.99.62). The default is the design's own pair and changes
nothing; any other face is a size-corrected alias so swapping one in doesn't break the layout."""
import re
from pathlib import Path

import pytest

from armada import appconfig, fonts

STATIC = Path(fonts.__file__).resolve().parent / "webui" / "static"


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path)); monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


def test_six_families_and_the_design_defaults():
    assert len(fonts.CHOICES) == 6
    assert fonts.DEFAULTS == {"body": "barlow", "heading": "barlow-condensed"}


def test_the_default_emits_nothing(home):
    assert fonts.style() == ""


def test_a_choice_is_saved_and_emitted_for_light_and_dark(home):
    assert fonts.save("body", "montserrat")["ok"]
    css = fonts.style()
    assert ':root,.armada-dark{' in css and '--font-body:"ARMADA Body Montserrat"' in css
    assert "--font-heading" not in css
    assert fonts.save("heading", "roboto")["ok"] and '--font-heading:"ARMADA Heading Roboto"' in fonts.style()


def test_unknown_values_are_refused_and_ignored(home):
    assert fonts.save("body", "comic-sans")["ok"] is False
    assert fonts.save("footer", "roboto")["ok"] is False
    appconfig.save({"font_body": "comic-sans"})
    assert fonts.selected("body") == "barlow"


def test_every_face_exists_with_its_licence_and_size_correction():
    css = (STATIC / "fonts.css").read_text(encoding="utf-8")
    for slug, label in fonts.CHOICES.items():
        assert (STATIC / "fonts" / f"OFL-{slug}.txt").is_file(), slug
        for w in (400, 500, 600, 700):
            assert (STATIC / "fonts" / f"{slug}-{w}.woff2").is_file(), (slug, w)
        for role in ("Body", "Heading"):
            rules = re.findall(r'@font-face\{font-family:"ARMADA ' + role + " " + re.escape(label) + r'";[^}]*\}', css)
            assert len(rules) == 4, (role, label)
            assert all("size-adjust:" in r and "ascent-override:" in r and "font-display:block" in r for r in rules)


def test_the_design_fonts_are_not_resized_in_their_own_role():
    css = (STATIC / "fonts.css").read_text(encoding="utf-8")
    assert 'font-family:"ARMADA Body Barlow";src:url(/static/fonts/barlow-400.woff2) format("woff2");font-weight:400;font-style:normal;font-display:block;size-adjust:100.0%' in css
    assert '"ARMADA Heading Barlow Condensed";src:url(/static/fonts/barlow-condensed-600.woff2)' in css


def test_the_picker_is_in_settings():
    src = (STATIC.parent / "pages.py").read_text(encoding="utf-8")
    assert "_font_picker()" in src and 'data-role="{role}"' in src
    js = (STATIC / "js/settings.js").read_text(encoding="utf-8")
    assert "document.querySelectorAll('.mc-fontpick select')" in js


@pytest.mark.parametrize('value', [None, True, False, '14', 14.5, 9, 27, [], {}])
def test_invalid_reference_sizes_cannot_replace_the_saved_size(home, value):
    assert fonts.save_size(18)['ok']
    assert not fonts.save_size(value)['ok']
    assert fonts.reference_size() == 18


def test_reference_size_persists_and_reset_keeps_the_font_families(home):
    fonts.save('body', 'roboto')
    assert fonts.reference_size() == 13
    assert fonts.save_size(26)['font_size'] == 26
    assert '--mc-font-reference:26' in fonts.style()
    assert '--mc-font-scale:2.00000000' in fonts.style()
    assert fonts.save_size(13)['ok']
    assert 'mc-font-scale' not in fonts.style()
    assert fonts.selected('body') == 'roboto'


def test_font_preference_write_failure_retains_the_exact_reason(home, monkeypatch):
    fonts.save_size(17)
    def fail(updates): raise PermissionError('Font preference is read-only')
    monkeypatch.setattr(appconfig,'save',fail)
    assert fonts.save_size(18) == {'ok':False,'error':'Font preference is read-only'}
    assert fonts.reference_size() == 17


@pytest.mark.parametrize('value', [None, '20', True, 999, {'bad':'value'}])
def test_invalid_saved_reference_size_uses_the_default(home, value):
    appconfig.save({'font_size':value})
    assert fonts.reference_size() == 13


@pytest.mark.parametrize('realm_mode', ['welcome', 'open', 'archived'])
def test_font_preferences_are_authenticated_app_settings_independent_of_realm(home, tmp_path, realm_mode):
    import json
    import threading
    import urllib.request
    import urllib.error
    from armada import local_auth, serve, util
    root = tmp_path/'realm'
    if realm_mode != 'welcome':
        util.write_json_atomic(root/'realm.json', {'name':'Font test', 'archived':realm_mode=='archived'})
    class Handler(serve.Handler):
        realm = str(root) if realm_mode != 'welcome' else None
    server = serve._Server(('127.0.0.1',0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
    url = f'http://127.0.0.1:{server.server_port}'
    headers = {**local_auth.headers(server.server_port), 'Content-Type':'application/json'}
    try:
        with pytest.raises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(url+'/api/font-size')
        assert denied.value.code == 401
        request = urllib.request.Request(url+'/api/save-appearance',
            data=json.dumps({'font_size':17}).encode(), headers=headers)
        with urllib.request.urlopen(request) as response:
            assert json.load(response) == {'ok':True,'font_size':17}
        with urllib.request.urlopen(urllib.request.Request(url+'/api/font-size',headers=headers)) as response:
            assert json.load(response) == {'font_size':17}
        request = urllib.request.Request(url+'/api/save-appearance',data=b'{"font_size":20}',
            headers={**headers,'Sec-Fetch-Site':'cross-site','Origin':'https://outside.test'})
        with pytest.raises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(request)
        assert denied.value.code == 403
        assert fonts.reference_size() == 17
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)


def test_font_size_keyboard_and_persistence_browser_controller():
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node: pytest.skip('Node required for keyboard controller checks')
    result = subprocess.run([node,str(Path(__file__).with_name('font_size_harness.js'))],
                            capture_output=True,text=True,timeout=15)
    assert result.returncode == 0, result.stderr
