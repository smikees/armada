"""Authenticode signing for the installer, its temporary copies and native payload.

ARMADA_SIGNING_CONFIG names a private JSON file with a command argument list containing
one {file} placeholder and the expected certificate subject in publisher. Credentials
belong in the signing provider's credential store, never in this file or command line.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess


def configuration() -> dict:
    path = os.environ.get('ARMADA_SIGNING_CONFIG')
    if not path:
        raise SystemExit('Windows signing is not configured. Set ARMADA_SIGNING_CONFIG; '
                         'only private local builds may use --allow-unsigned.')
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    command = data.get('command')
    if (not isinstance(command, list) or not command or
            not all(isinstance(arg, str) and arg for arg in command) or
            sum(arg.count('{file}') for arg in command) != 1 or
            not isinstance(data.get('publisher'), str) or not data['publisher'].strip()):
        raise SystemExit('Signing config requires command argv with one {file} and publisher subject.')
    return data


def signatures(paths: list[Path]) -> list[dict]:
    if not paths:
        return []
    # Pass filenames as JSON through stdin: no shell interpolation, even for quotes in paths.
    script = ("$ErrorActionPreference='Stop'; "
        "Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Security/Microsoft.PowerShell.Security.psd1'); "
        "$items=ConvertFrom-Json ([Console]::In.ReadToEnd()); "
        "$result=@(foreach($path in $items) { $s=Get-AuthenticodeSignature -LiteralPath $path; "
        "[pscustomobject]@{path=$path; status=[string]$s.Status; "
        "subject=$s.SignerCertificate.Subject; issuer=$s.SignerCertificate.Issuer; "
        "timestamp=[bool]$s.TimeStamperCertificate} }); "
        "ConvertTo-Json -InputObject $result -Compress")
    result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
                            input=json.dumps([str(p.resolve()) for p in paths]),
                            capture_output=True, text=True, check=True, timeout=180)
    return json.loads(result.stdout)


def require_valid(record: dict, *, publisher: str | None = None) -> None:
    if (record['status'] != 'Valid' or not record.get('subject') or
            record['subject'] == record.get('issuer')):
        raise SystemExit(f"Untrusted Authenticode signature: {Path(record['path']).name}")
    if publisher is not None and (record['subject'] != publisher or not record.get('timestamp')):
        raise SystemExit(f"Wrong publisher or missing timestamp: {Path(record['path']).name}")


def sign_file(path: Path, config: dict | None = None) -> None:
    config = config or configuration()
    command = [arg.replace('{file}', str(path.resolve())) for arg in config['command']]
    # Some providers print credentials in diagnostics: never relay command/output on failure.
    try:
        result = subprocess.run(command, capture_output=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired):
        raise SystemExit(f'Signing could not complete: {path.name}') from None
    if result.returncode:
        raise SystemExit(f'Signing failed for {path.name} (exit {result.returncode}); check the provider locally.')
    require_valid(signatures([path])[0], publisher=config['publisher'])


def native_files(root: Path) -> list[Path]:
    """Find PE images by header, including .pyd/.dll files and extensionless executables."""
    result = []
    for path in sorted(root.rglob('*')):
        if path.is_file():
            with path.open('rb') as stream:
                if stream.read(2) == b'MZ':
                    result.append(path)
    return result


def sign_payload(root: Path, config: dict) -> None:
    paths = native_files(root)
    for path, record in zip(paths, signatures(paths), strict=True):
        if record['status'] == 'NotSigned':
            sign_file(path, config)
        else:
            # Preserve upstream publisher signatures; never hide a broken one by re-signing.
            require_valid(record)
    for record in signatures(paths):
        require_valid(record)


def inno_command(python: Path, helper: Path) -> str:
    # Inno substitutes $f with its quoted temporary filename. Escape its own $/quote syntax.
    def quote(path):
        return '$q' + str(path).replace('$', '$$').replace('"', '$q') + '$q'
    return f'{quote(python)} {quote(helper)} $f'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    sign_file(parser.parse_args().file)
