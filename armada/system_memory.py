"""Read-only installation-wide instructions, loaded afresh for every agent turn."""
from dataclasses import dataclass
from pathlib import Path

from . import appconfig

MAX_LENGTH = 16000
DEFAULT_PATH = Path(__file__).with_name('system-memory.txt')


@dataclass(frozen=True)
class SystemMemory:
    title: str
    text: str
    path: Path


def _validate(text):
    if not isinstance(text, str) or len(text) > MAX_LENGTH or '\x00' in text:
        raise ValueError(f'ARMADA system memory must be text of at most {MAX_LENGTH:,} characters, without NUL characters.')
    return text


def load() -> SystemMemory:
    config = appconfig._read()
    # Preserve instructions saved with the former app editor, including explicit empty text.
    if 'system_memory' in config:
        return SystemMemory('Owner instructions', _validate(config['system_memory']), appconfig._path())
    return SystemMemory('ARMADA inbox timing', _validate(DEFAULT_PATH.read_text(encoding='utf-8')), DEFAULT_PATH)


def prompt():
    text = load().text.strip()
    return '# ARMADA system memory — owner instructions for all realms\n' + text if text else ''
