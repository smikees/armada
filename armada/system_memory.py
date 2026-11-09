"""Owner-managed installation-wide instructions, loaded afresh for every agent turn."""
import hashlib

from . import appconfig, clock, util

MAX_LENGTH = 16000
DEFAULT = '''ARMADA inbox timing
When delegating a task, you may add optional JSON fields process_after and process_before
to the inbox message. Prefer ISO timestamps with explicit UTC offsets, for example
"process_after": "2026-11-10T09:00:00+01:00". MM/DD/YYYY HH:MM:SS is also accepted;
without an offset, it uses the recipient realm's timezone (or the machine timezone if unset).
Standalone lines in the ask, such as "process after 11/10/2026 09:00:00", also work.
Use a separate line for each timing instruction. Structured fields and lines must agree.
ARMADA keeps future items pending and does not offer them as tasks before their time.
It never starts an expired task. Both bounds are strict: after < start time < before.
Only the owner can use Process now and acknowledge the displayed timing warning to override
a valid window for that one task. Agents must not treat that as a general timing exemption.
Process before limits when work may start; it does not stop work that has already started.
The normal inbox cadence and execution capacity still apply; a timing window does not
guarantee execution at an exact time. Invalid, ambiguous or conflicting times are refused.
Do not read ahead and execute deferred inbox tasks or bypass their timing through another run.
These instructions never grant tools, permissions or approval. Respect the owner's access rules.
'''


def _revision(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _validate(text):
    if not isinstance(text, str) or len(text) > MAX_LENGTH or '\x00' in text:
        raise ValueError(f'ARMADA system memory must be text of at most {MAX_LENGTH:,} characters, without NUL characters.')
    return text


def load():
    text = _validate(appconfig._read().get('system_memory', DEFAULT))
    return {'text': text, 'revision': _revision(text)}


def prompt():
    text = load()['text'].strip()
    return '# ARMADA system memory — owner instructions for all realms\n' + text if text else ''


def save(text, revision):
    text = _validate(text)
    path = appconfig._path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with util.file_lock(path):
        cfg = appconfig._read()
        old = _validate(cfg.get('system_memory', DEFAULT))
        if revision != _revision(old):
            raise ValueError('System memory changed in another window. Reload before saving.')
        cfg.update(system_memory=text, system_memory_changed_at=clock.now().isoformat())
        util.write_json_atomic(path, cfg)
    return {'ok': True, 'revision': _revision(text)}
