"""Machine realm discovery with one strict, exclusive mutation boundary."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path

from . import util


def path() -> Path:
    return util.data_dir() / "realms.json"


def identity(value: str) -> Path:
    return Path(value).resolve()


def _validate(items):
    if not isinstance(items, list):
        raise util.StateError("Realm registry must be a list; original file preserved.")
    seen = set()
    for record in items:
        if (not isinstance(record, dict) or not isinstance(record.get("path"), str)
                or not record["path"].strip() or not Path(record["path"]).is_absolute()
                or not isinstance(record.get("name", ""), str)):
            raise util.StateError("Invalid realm registry entry; original file preserved.")
        key = identity(record["path"])
        if key in seen:
            raise util.StateError("Duplicate realm registry entry; original file preserved.")
        seen.add(key)
    return items


def load() -> list[dict]:
    try:
        raw = path().read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return []
    except (OSError, UnicodeError) as exc:
        raise util.StateError("Cannot read the realm registry; original file preserved.") from exc
    try:
        return _validate(json.loads(raw))
    except (ValueError, TypeError) as exc:
        raise util.StateError("Invalid realm registry JSON; original file preserved.") from exc


@contextmanager
def edit():
    """Commit validated changes only after the entire operation succeeds under the lock."""
    with util.file_lock(path(), validate_state=False):
        records = load()
        original = deepcopy(records)
        yield records
        _validate(records)
        if records != original:
            util.write_json_atomic(path(), records)


def ensure(folder: str, name: str):
    target = identity(folder)
    with edit() as records:
        if not any(identity(record["path"]) == target for record in records):
            records.append({"path": str(target), "name": name})


def rename_in(records, folder: str, name: str):
    target = identity(folder)
    for record in records:
        if identity(record["path"]) == target:
            record["name"] = name


def rename(folder: str, name: str):
    with edit() as records:
        rename_in(records, folder, name)
