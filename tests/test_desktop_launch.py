"""Application lifetime is independent of the selected realm and calling tool."""
from pathlib import Path
from unittest.mock import Mock

import pytest

from armada import cli, desktop_launch


@pytest.mark.parametrize('args', [
    ['app'],
    ['app', r'D:\Realms\Cabinet'],
    ['app', r'D:\Realms\Another', '--port', '8876'],
])
def test_cli_detaches_before_reading_realm_configuration(monkeypatch, args):
    relaunch = Mock(return_value=True)
    monkeypatch.setattr(desktop_launch, 'relaunch_if_needed', relaunch)
    assert cli.main(args) == 0
    relaunch.assert_called_once_with(args)


@pytest.mark.skipif(desktop_launch.os.name != 'nt', reason='Windows desktop ownership')
def test_relaunch_preserves_realm_args_and_uses_standalone_host(monkeypatch, tmp_path):
    host = tmp_path/'ARMADA.exe'
    host.touch()
    monkeypatch.setattr(desktop_launch.sys, 'executable', str(tmp_path/'pythonw.exe'))
    monkeypatch.setattr(desktop_launch, 'desktop_parent', lambda: False)
    spawn = Mock(return_value=123)
    monkeypatch.setattr(desktop_launch, 'spawn', spawn)
    args = ['app', r'D:\Realms\Different realm']
    assert desktop_launch.relaunch_if_needed(args)
    spawn.assert_called_once_with([str(host), '-m', 'armada', *args])


def test_already_independent_app_does_not_spawn_another_instance(monkeypatch):
    monkeypatch.setattr(desktop_launch, 'desktop_parent', lambda: True)
    spawn = Mock()
    monkeypatch.setattr(desktop_launch, 'spawn', spawn)
    assert not desktop_launch.relaunch_if_needed(['app'])
    spawn.assert_not_called()
