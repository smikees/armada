"""Theme selection, custom typography and ready-cue regressions."""
import ctypes
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from armada import appconfig, fonts, serve, startup_sound, vtheme
from armada.webui import layout


def test_theme_selection_saves_typography_together_and_keeps_other_preferences():
    appconfig.save({'appearance':'dark', 'startup_sound':False, 'unrelated':'retained'})
    handler = object.__new__(serve.Handler)
    assert handler._save_appearance({'theme':'armada-ii'})['ok']
    assert appconfig.get('theme') == 'armada-ii'
    assert fonts.selected('body') == fonts.selected('heading') == 'ibm-plex-sans'
    assert fonts.reference_size() == fonts.default_size() == 15
    assert appconfig.get('appearance') == 'dark' and appconfig.get('startup_sound') is False
    assert appconfig.get('unrelated') == 'retained'
    assert handler._save_appearance({'theme':'armada'})['ok']
    assert fonts.selected('heading') == 'barlow-condensed'
    assert fonts.reference_size() == fonts.default_size() == 13


def test_theme_defaults_work_when_only_the_theme_is_present():
    appconfig.save({'theme':'armada-ii'})
    assert fonts.selected('body') == fonts.selected('heading') == 'ibm-plex-sans'
    assert fonts.reference_size() == fonts.default_size() == 15


def test_old_default_faces_can_override_the_new_theme():
    handler = object.__new__(serve.Handler)
    handler._save_appearance({'theme':'armada-ii'})
    fonts.save('body','barlow')
    fonts.save('heading','barlow-condensed')
    style = layout._theme_style()
    assert '--font-body:"ARMADA Body Barlow"' in style
    assert '--font-heading:"ARMADA Heading Barlow Condensed"' in style


def test_bad_theme_and_sound_values_preserve_saved_preferences():
    handler = object.__new__(serve.Handler)
    handler._save_appearance({'theme':'armada-ii'})
    before = appconfig.load()
    assert not handler._save_appearance({'theme':'untrusted'})['ok']
    assert not handler._save_appearance({'startup_sound':'false'})['ok']
    assert appconfig.load() == before
    assert handler._save_appearance({'startup_sound':False})['ok']
    assert appconfig.get('startup_sound') is False


def test_sound_is_started_once_off_thread_and_can_be_disabled(monkeypatch):
    monkeypatch.delenv('ARMADA_NO_EXTERNAL_NOTIFY', raising=False)
    monkeypatch.setattr(startup_sound,'_started',False)
    monkeypatch.setattr(startup_sound.sys,'platform','win32')
    thread = Mock()
    monkeypatch.setattr(startup_sound.threading,'Thread',thread)
    startup_sound.play();startup_sound.play()
    assert thread.call_count == 1 and thread.return_value.start.call_count == 1
    assert thread.call_args.kwargs['daemon'] is True
    monkeypatch.setattr(startup_sound,'_started',False)
    appconfig.save({'startup_sound':False})
    startup_sound.play()
    assert thread.call_count == 1


@pytest.mark.parametrize('fail_at', [None,'open','setaudio','play'])
def test_native_playback_is_quiet_closes_devices_and_never_raises(monkeypatch, fail_at):
    commands = []
    def command(text, *_):
        commands.append(text)
        return 5 if fail_at and text.startswith(fail_at) else 0
    monkeypatch.setattr(ctypes,'WinDLL',lambda _:SimpleNamespace(mciSendStringW=command),raising=False)
    startup_sound._play_windows()
    assert commands[0].startswith('open "')
    if fail_at != 'open':
        assert 'volume to 120' in commands[1]
        assert commands[-1].startswith('close ')
    else:
        assert len(commands) == 1


def test_sound_asset_and_mono_faces_are_packaged():
    assert startup_sound.SOUND.is_file() and startup_sound.SOUND.stat().st_size > 0
    static = Path(fonts.__file__).parent/'webui/static'
    assert (static/'fonts/OFL-ibm-plex-mono.txt').is_file()
    for weight in (400,500,600,700):
        assert (static/f'fonts/ibm-plex-mono-{weight}.woff2').is_file()
