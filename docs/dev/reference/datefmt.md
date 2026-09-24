# `armada/datefmt.py`

Dates and times, one way everywhere (DESIGN_SYSTEM §9a, UI audit C2).

The month is always a word and times are 24-hour: `9/24` and `24/9` read differently to different
owners, `24 Sep` doesn't. Six formats had grown up across the app (`Thu 9/24, 22:30`, `17/09/26`,
`19-09-26 14:40`, `21-09-26`, `01 Oct 2027`, `Thu 24th`); these four replace them. The names are
fixed English rather than strftime's %b/%a, which follow the machine's locale on Windows and would
turn "Sep" into "sept." on a Spanish install. `static/js/sysjobs.js` mirrors `moment()`.

### `_today(today=None)`

—

### `moment(t: _dt.datetime)`

A moment near now — next run, last run: `Thu 24 Sep, 22:30`.

### `day(d, today=None, year: bool=False)`

A date: `24 Sep` this year, `1 Oct 2027` otherwise — or always with the year when it matters (an ETA, an appointment): `year=True`.

### `stamp(t: _dt.datetime, today=None)`

A timestamp in a list (artefacts, run history): `19 Sep, 14:40`; the year only if it isn't this one: `19 Sep 2025, 14:40`.

### `parse(s)`

ISO text (with or without time or `Z`) → datetime, or None.
