# `armada/support.py`

Report an issue (launch plan 5.6, ADR-005).

The beta's one feedback path: the support icon beside the settings gear opens a short form; ARMADA
assembles a report — the person's words, the page they were on, the version, and (if they agree) the
last lines of its logs with anything that looks like a secret removed — **shows them the whole
report**, and only when they press Send does it email it to the beta inbox.

Three rules shape this module:

- **What's sent is exactly what was shown.** `preview()` builds the text and hands back a token;
  `send()` sends the text stored under that token, not a rebuild. Logs move on in the seconds between
  the two, and "we showed you one thing and sent another" is the worst thing a report button can do.
- **Nothing secret leaves.** Log lines pass through `redact()`: API keys, bearer and OAuth tokens,
  Telegram bot tokens, long secret-shaped strings, email addresses other than the one the person
  typed, and the Windows user name in paths.
- **The key can only send.** The Resend key is a sending-only key restricted to armada.stamih.com
  (ADR-005: fine for five invited users; a relay before a public release). It lives in
  `armada/support_key.txt`, which is git-ignored and written by the build; it is never in the repo.

Sending is a network call, so it happens only on the POST from the Send button — never while a page
renders.

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

### `key()`

The sending key: ARMADA_RESEND_KEY (for a developer), else the file the build writes.

### `_sent_log()`

—

### `_recent_sends()`

—

### `_save_unsent(rep: dict)`

Keep a report that couldn't be sent, so nothing the person wrote is lost.

### `_post(payload: dict, k: str, timeout: int=20)`

—

### `send(token: str)`

Send the previewed report. On any failure the report is saved locally and the person is told where, and to email it themselves — the words they took the trouble to write are never lost.
