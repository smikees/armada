"""Owner-managed command credentials outside realms; never returned by an API."""
import base64
import hashlib
import os
from pathlib import Path
import re
from . import util


def _path():
    return util.data_dir() / 'command-secrets.json'


def _scope(root):
    return hashlib.sha256(str(Path(root).resolve()).casefold().encode()).hexdigest()


def _read(root):
    return util.read_json_state(_path(), default=dict).get(_scope(root), {})


def names(root):
    return sorted(_read(root))


def save(root, name, value):
    if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', name):
        raise ValueError('Secret names use lowercase letters, numbers and underscores.')
    if not isinstance(value, str) or len(value) > 32768 or '\0' in value:
        raise ValueError('Enter a valid secret value of at most 32768 characters.')
    path = _path()
    if (path.resolve().is_relative_to(Path(root).resolve())
            or any((parent/'realm.json').is_file() or (parent/'cabinet/schedule.json').is_file() for parent in path.resolve().parents)):
        raise ValueError('Credential storage must be outside every realm folder.')
    if value and os.name != 'nt':
        raise ValueError('Encrypted command credentials currently require Windows.')
    from .provider_keys import _crypt
    with util.file_lock(path):
        data = util.read_json_state(path, default=dict)
        bucket = data.setdefault(_scope(root), {})
        if value:
            bucket[name] = 'dpapi:' + base64.b64encode(_crypt(value.encode())).decode('ascii')
        else:
            bucket.pop(name, None)
        util.write_json_atomic(path, data)
        os.chmod(path, 0o600)
    from .run_policy import audit
    audit('command-secret', root, name=name, configured=bool(value))
    return names(root)


def environment(root, agent, job):
    requested = job.get('secrets', [])
    if not requested:
        return {}
    from .run_policy import verify_job
    if job.get('kind') != 'command' or not verify_job(root, agent, job):
        raise ValueError('Command secrets require an owner-approved command job.')
    from .provider_keys import _crypt
    stored = _read(root)
    result = {}
    for name in requested:
        value = stored.get(name, '')
        if not value.startswith('dpapi:'):
            raise ValueError(f'Configure command secret {name} in App Settings before running this job.')
        result['ARMADA_SECRET_' + name.upper()] = _crypt(base64.b64decode(value[6:]), decrypt=True).decode('utf-8')
    return result


def redact(text, values):
    for value in sorted(values, key=len, reverse=True):
        if value:
            text = text.replace(value, '[secret redacted]')
    return text
