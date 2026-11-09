"""Processing windows for delegated tasks; evaluated before any recipient model call."""
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

from . import clock, util

FIELDS = ('process_after', 'process_before')
_DIRECTIVE = re.compile(r'^\s*process\s+(after|before)\s*:?[ \t]+(.+?)\s*$', re.I | re.M)


def timestamp(value, root):
    try:
        return _timestamp(value, root)
    except OverflowError as exc:
        raise ValueError('That timestamp is outside the supported date range after timezone conversion.') from exc


def _timestamp(value, root):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Timing must be a timestamp, not an empty value.')
    value = value.strip()
    try:
        if re.fullmatch(r'\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}', value):
            parsed = dt.datetime.strptime(value, '%m/%d/%Y %H:%M:%S')
        elif re.fullmatch(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?', value):
            parsed = dt.datetime.fromisoformat(value)
        else:
            raise ValueError()
    except ValueError as exc:
        raise ValueError('Use MM/DD/YYYY HH:MM:SS or an ISO timestamp with an offset.') from exc
    if parsed.tzinfo is None:
        from .scheduler import _tz
        zone = _tz(util.read_json_state(Path(root) / 'realm.json', default=dict))
        if zone is None:
            # Resolve both folds using the machine's rules at the requested date.
            candidates = {parsed.replace(fold=f).astimezone().astimezone(dt.timezone.utc)
                          for f in (0, 1)
                          if parsed.replace(fold=f).astimezone().replace(tzinfo=None) == parsed}
            if len(candidates) != 1:
                raise ValueError('That local time is ambiguous or does not exist; use an explicit UTC offset.')
            aware = candidates.pop()
        else:
            candidates = {parsed.replace(tzinfo=zone, fold=f).astimezone(dt.timezone.utc)
                          for f in (0, 1)
                          if parsed.replace(tzinfo=zone, fold=f).astimezone(dt.timezone.utc)
                          .astimezone(zone).replace(tzinfo=None) == parsed}
            if len(candidates) != 1:
                raise ValueError('That local time is ambiguous or does not exist; use an explicit UTC offset.')
            aware = candidates.pop()
        parsed = aware
    return parsed.astimezone(dt.timezone.utc)


def window(root, message):
    """Structured fields and standalone instruction lines must agree; never guess."""
    values = {key: [message[key]] if key in message else [] for key in FIELDS}
    for line in str(message.get('ask', '')).splitlines():
        if re.match(r'^\s*process\s+(?:after|before)\b', line, re.I):
            match = _DIRECTIVE.fullmatch(line)
            if not match:
                raise ValueError('A process after/before instruction needs a timestamp.')
            edge, value = match.groups()
            values['process_' + edge.lower()].append(value)
    result = {}
    for key, entries in values.items():
        stamps = {timestamp(value, root) for value in entries}
        if len(stamps) > 1:
            raise ValueError(f'Conflicting {key} timestamps.')
        if stamps:
            result[key] = stamps.pop()
    if len(result) == 2 and result[FIELDS[0]] >= result[FIELDS[1]]:
        raise ValueError('Process after must be earlier than process before.')
    return result


def normalized(root, message):
    return {key: value.isoformat(timespec='microseconds') for key, value in window(root, message).items()}


def status(root, message, now=None):
    """eligible, deferred, expired or invalid; malformed timing is never eligible."""
    try:
        limits = window(root, message)
    except (ValueError, OSError) as exc:
        return 'invalid', 'Invalid inbox timing: ' + str(exc)
    now = (now or clock.now()).astimezone(dt.timezone.utc)
    before, after = limits.get('process_before'), limits.get('process_after')
    if before and now >= before:
        return 'expired', 'Processing window expired: process before ' + before.isoformat()
    if after and now <= after:
        return 'deferred', 'Waiting: process after ' + after.isoformat()
    return 'eligible', ''


def require_eligible(root, message):
    state, detail = status(root, message)
    if state != 'eligible':
        raise util.StateError(detail)


def confirmation(message):
    """Bind owner acknowledgement to the exact message shown, not just its id."""
    data = {k: v for k, v in message.items() if not k.startswith('_')}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def description(root, message):
    limits = window(root, message)
    lines = []
    originals = message.get('timing_original')
    originals = originals if isinstance(originals, dict) else {}
    for key, value in limits.items():
        original = originals.get(key, message.get(key))
        try:
            label = original if timestamp(original, root) == value else value.isoformat()
        except (OSError, ValueError):
            label = value.isoformat()
        lines.append(key.replace('_', ' ').capitalize() + ': ' + label)
    return '\n'.join(lines)
