"""Open the current setup wizard in a fresh, independent desktop test profile.

Uses installed ARMADA's runtime and the working tree's source. Armada state is
isolated; CLI discovery and authentication use the real Windows user profile.
No credentials are copied and existing realms/settings are untouched.
Usage: python tools/review_setup.py
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def isolate_armada_state(profile: Path):
    """Keep vendor homes/login stores intact; redirect only Armada's machine data."""
    profile.mkdir(parents=True, exist_ok=True)
    os.environ.update(ARMADA_DATA_DIR=str(profile.resolve() / '.armada'), ARMADA_MUTE_NOTIFICATIONS='1')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child', type=Path)
    parser.add_argument('--resume', type=Path, help='Reuse a prior setup review folder')
    args = parser.parse_args()
    if args.child is None:
        from armada.desktop_launch import spawn
        host = Path(os.environ['LOCALAPPDATA']) / 'Programs/ARMADA/python/ARMADA.exe'
        if not host.is_file():
            raise SystemExit('Install ARMADA first; its bundled desktop runtime is required.')
        run = args.resume.resolve() if args.resume else Path(tempfile.mkdtemp(prefix='setup-review-', dir=ROOT / 'build'))
        if not run.is_dir() or not run.is_relative_to(ROOT / 'build'):
            raise SystemExit('The review folder must exist under this checkout’s build directory.')
        pid = spawn([host, Path(__file__).resolve(), '--child', run], cwd=ROOT)
        print(json.dumps({'pid': pid, 'run': str(run)}))
        return

    run = args.child.resolve()
    profile = run / 'profile'
    # Spawn supplies Explorer's environment and device map. Keep HOME,
    # USERPROFILE, LOCALAPPDATA and provider config homes exactly as Windows uses
    # them; isolate only Armada's registry, configuration, logs and test realms.
    from armada.engine import get_engine
    binaries = {p: get_engine(p)._launcher() for p in ('claude', 'codex', 'gemini')}
    isolate_armada_state(profile)
    dirs = [str(Path(cmd[0]).parent) for cmd in binaries.values() if cmd]
    os.environ['PATH'] = os.pathsep.join(dirs + [os.environ.get('PATH', '')])
    from armada import appconfig, approot
    appconfig.save({'auto_update': False})
    (profile / 'ARMADA').mkdir(exist_ok=True)
    if not approot.configured():
        approot.set_root(str(profile / 'ARMADA'))
    from armada import providers
    if binaries.get('gemini'):
        providers._save('gemini', executable_path=binaries['gemini'][0])
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    (run / 'review.json').write_text(json.dumps({'pid': os.getpid(), 'port': port,
        'url': f'http://127.0.0.1:{port}/', 'profile': str(profile),
        'windows_home': str(Path.home()), 'cli_launchers': binaries}), encoding='utf-8')
    from armada import app
    raise SystemExit(app.run('', port=port, title='ARMADA — Setup review'))


if __name__ == '__main__':
    main()
