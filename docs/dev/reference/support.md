# `armada/support.py`

Send exactly the approved, redacted report through ARMADA's public relay.

Only the server holds the mail credential. A failed or uncertain send retains the preview
and saves a local copy; retries use one stable idempotency ID.

### `redact(text: str, keep_email: str='')`

Strip what shouldn't leave the machine from log text. Conservative on purpose: a report with a few too many [redacted] marks is still useful; one with a key in it is an incident.

### `_tail(path: Path, n: int)`

—

### `_facts(realm_root: str)`

—

### `build(realm_root: str, message: str, page: str='', title: str='', email: str='', include_logs: bool=True)`

The report as it will be sent: {subject, text}. Pure — it reads, it sends nothing.

### `preview(realm_root: str, **kw)`

Build the report and keep it under a token, so Send sends exactly this text.

### `_save_unsent(rep: dict)`

Keep a report that couldn't be sent, so nothing the person wrote is lost.

### class `_NoRedirect`

—

- `_NoRedirect.redirect_request(self, req, fp, code, msg, headers, newurl)` — —

### `_post(payload: dict)`

—

### `send(token: str)`

Send the approved snapshot, preserving the same ID across uncertain-delivery retries.
