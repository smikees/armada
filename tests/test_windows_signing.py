"""Public builds must reject missing trust and sign Inno's internal executable too."""
import json
from pathlib import Path
import subprocess

import pytest

from tools import sign_windows as signing


def record(path, status='Valid', subject='CN=Publisher', issuer='CN=Trusted CA', timestamp=True):
    return dict(path=str(path), status=status, subject=subject, issuer=issuer, timestamp=timestamp)


def test_missing_configuration_blocks_public_build(monkeypatch):
    monkeypatch.delenv('ARMADA_SIGNING_CONFIG', raising=False)
    with pytest.raises(SystemExit, match='not configured'):
        signing.configuration()


@pytest.mark.parametrize('command', ['sign file', ['sign'], ['sign', '{file}', '{file}'], [1, '{file}']])
def test_configuration_requires_an_argument_list_and_exactly_one_target(tmp_path, monkeypatch, command):
    path = tmp_path / 'signing.json'
    path.write_text(json.dumps(dict(command=command, publisher='CN=Publisher')))
    monkeypatch.setenv('ARMADA_SIGNING_CONFIG', str(path))
    with pytest.raises(SystemExit, match='command argv'):
        signing.configuration()


@pytest.mark.parametrize('change', [dict(status='NotSigned'), dict(status='HashMismatch'),
    dict(subject='CN=Other'), dict(timestamp=False), dict(issuer='CN=Publisher')])
def test_signing_requires_expected_trusted_publisher_and_timestamp(change):
    info = record('setup.exe') | change
    with pytest.raises(SystemExit):
        signing.require_valid(info, publisher='CN=Publisher')


def test_signing_preserves_argument_boundaries_and_verifies_result(tmp_path, monkeypatch):
    file = tmp_path / "a '$quote.dll"
    file.write_bytes(b'MZ')
    def run(argv, **kwargs):
        assert argv == ['signer.exe', '--target', str(file.resolve())]
        assert kwargs['capture_output'] and 'shell' not in kwargs
        return subprocess.CompletedProcess(argv, 0)
    monkeypatch.setattr(signing.subprocess, 'run', run)
    monkeypatch.setattr(signing, 'signatures', lambda paths: [record(paths[0])])
    signing.sign_file(file, dict(command=['signer.exe', '--target', '{file}'], publisher='CN=Publisher'))


def test_signing_failure_does_not_echo_provider_output(monkeypatch):
    monkeypatch.setattr(signing.subprocess, 'run', lambda *a, **k:
        subprocess.CompletedProcess(['private'], 1, b'secret', b'secret'))
    with pytest.raises(SystemExit) as error:
        signing.sign_file(Path('file.exe'), dict(command=['sign', '{file}'], publisher='CN=Publisher'))
    assert 'secret' not in str(error.value) and 'private' not in str(error.value)


def test_payload_signs_unsigned_native_modules_and_preserves_upstream(tmp_path, monkeypatch):
    for name in ('app.exe', '_native.pyd', 'vendor.dll', 'helper'):
        (tmp_path / name).write_bytes(b'MZpayload')
    (tmp_path / 'source.py').write_text('print(1)')
    signed = []
    def inspect(paths):
        return [record(p, 'Valid' if p.name == 'vendor.dll' or p in signed else 'NotSigned') for p in paths]
    monkeypatch.setattr(signing, 'signatures', inspect)
    monkeypatch.setattr(signing, 'sign_file', lambda p, c: signed.append(p))
    signing.sign_payload(tmp_path, {'publisher': 'CN=Publisher'})
    assert {p.name for p in signed} == {'app.exe', '_native.pyd', 'helper'}


def test_payload_refuses_invalid_upstream_signature(tmp_path, monkeypatch):
    (tmp_path/'vendor.dll').write_bytes(b'MZbroken')
    monkeypatch.setattr(signing, 'signatures', lambda paths: [record(paths[0], 'HashMismatch')])
    monkeypatch.setattr(signing, 'sign_file', lambda *a: pytest.fail('Do not replace invalid signatures'))
    with pytest.raises(SystemExit, match='Untrusted'):
        signing.sign_payload(tmp_path, {'publisher':'CN=Publisher'})


def test_inno_signing_includes_the_extracted_temporary_executable():
    root = Path(__file__).resolve().parents[1]
    script = (root/'installer'/'armada.iss').read_text(encoding='utf-8')
    section = script.split('#ifdef SignWindows')[1].split('#endif')[0]
    assert 'SignTool=ArmadaSigning' in section and 'SignedUninstaller=yes' in section
    command = signing.inno_command(Path('C:/With Space/python.exe'), Path('C:/With $/sign.py'))
    assert command.startswith('$q' + str(Path('C:/With Space/python.exe')) + '$q ')
    assert command.endswith(' $f') and '$$' in command


def test_public_builder_never_requests_unsigned_output():
    root = Path(__file__).resolve().parents[1]
    assert '--allow-unsigned' not in (root/'tools'/'publish_release.py').read_text()
