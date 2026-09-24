# `armada/realmformat.py`

The realm's on-disk format version, and the one place that upgrades it.

A realm is a folder someone keeps for years and carries between machines — and between versions of
ARMADA. Every field added to `realm.json` this month (sections, toolkit, usage_epoch, the notify
settings, the workspace root…) was added the same way: readers default the missing key, writers add
it the next time they save. That holds up until the first change that ISN'T additive — a renamed
key, a split file, a value whose meaning changes — at which point there is no way to tell a realm
written before the change from one written after, and "default the missing key" silently reads an
old realm as if it were new.

So `realm.json` carries an integer `schema_version`, and `migrate()` walks a realm from whatever
version it is at up to `CURRENT`, one registered step at a time. It runs when a realm is opened
(server start, switching realms, the scheduler's pass) and when one is imported (adopting an
existing folder). The first step, 0 → 1, changes nothing but the stamp: it exists so that every
realm on disk states its version before any migration that actually does something is needed.

Rules a migration step follows:

- It receives the parsed `realm.json` dict and the realm root, and returns the new dict. It may
  touch other files in the realm, but must be idempotent — a step interrupted halfway (a crash, a
  locked file) will run again from the start on the next open.
- It never runs on a realm whose version is NEWER than this build knows (`CURRENT`): a realm opened
  by a newer ARMADA and then by an older one must not be "upgraded" backwards by code that doesn't
  understand it. That case is reported, and the realm is left exactly as it is.
- Nothing here raises to the caller. A realm that can't be migrated still opens — the app falls
  back to the tolerant readers it has always had — and the reason is logged.

Legacy stamp: realms scaffolded before this module existed carry `"schema_version": "0.1"` (a
string, never read by anything). It described the same format as an unstamped realm, so it counts
as version 0 and gets restamped as the integer 1.

### `_m0_to_1(cfg: dict, realm_root: Path)`

0 → 1: no change to the data. Stamps the version so every realm states one from here on.

### `_renamed_run(run)`

A command job's `run` with `-m matcap` → `-m armada`, or None if it has no such call.

### `_m1_to_2(cfg: dict, realm_root: Path)`

1 → 2: the app's internal name changed from `matcap` to `armada` (ADR-010).

### `version_of(cfg)`

The version a parsed realm.json is at. Unstamped, the legacy "0.1", or unreadable → 0.

### `_stamp(cfg: dict, version: int)`

Return cfg with schema_version set, placed right after `name` (or first) so it's visible.

### `plan(cfg)`

What migrate() would do to this config, without doing it: {from, to, steps, newer}.

### `migrate(realm_root)`

Bring `realm_root`'s realm.json up to CURRENT. Never raises.

### `ensure(realm_root)`

migrate() once per realm per change to its realm.json. Cheap on the hot path: one stat().
