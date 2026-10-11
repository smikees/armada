"""Inspector agents carry the scan-search mark beside their name; others don't."""
import json

from armada.icons import ICONS
from armada.webui.agentbits import _inspector_mark


def test_only_inspector_agents_get_the_mark(tmp_path):
    for aid, flag in (("feynman", True), ("warren", False)):
        d = tmp_path / "agents" / aid
        d.mkdir(parents=True)
        (d / "agent.json").write_text(json.dumps({"id": aid, "is_inspector": flag}), encoding="utf-8")
    assert "scan-search" in ICONS
    mark = _inspector_mark(tmp_path, "feynman", 16)
    assert 'class="mc-inspector-mark"' in mark and 'aria-label="Inspector"' in mark
    assert _inspector_mark(tmp_path, "warren", 16) == "" and _inspector_mark(tmp_path, "nobody", 16) == ""


def test_the_ready_sound_switch_lives_under_advanced():
    from armada.webui import pages

    class _Upd:
        @staticmethod
        def auto_enabled():
            return True

        @staticmethod
        def installed():
            return False
    html = pages._app_advanced(_Upd())
    assert 'id="st-startup-sound"' in html and "Play a quiet sound when ARMADA is ready" in html
    assert 'class="mc-startup-sound"' not in pages._font_picker()
