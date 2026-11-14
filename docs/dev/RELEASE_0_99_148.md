# v0.99.148 — connector outage recovery and guarded job starts

Release preparation, 14 November 2026. Publication is owner-authorized. This
release adds the [outage-recovery controls](BROKER_RELIABILITY.md), including
connector health monitoring, durable start waits, dependent job windows, custom
retry delays, approved fallback jobs, coordinator opt-in/caps and command secrets.
The owner explicitly deferred live IBKR sign-in and accepted the same-user Windows
credential boundary. No live realm, job, broker registration or gateway is changed.

Implementation validation passed 4,626 tests with six skips, the stabilization
gate and an 11-check native form journey. Release validation must repeat on the
final source commit and staged runtime; results will be recorded here after publication.

Provider defaults were reviewed against live Claude metadata, cached Codex
metadata and the connected Gemini CLI catalogue. Selection still requires a connected provider and an available model;
otherwise its provider default is used. Runtime compatibility remains unchanged:
Python 3.14.10 matches the latest published 3.14 maintenance release checked at
[python.org](https://www.python.org/downloads/release/python-31410/).

This follows the established owner-authorized maintenance beta distribution.
Update assets are Ed25519-signed; trusted Windows publisher signing and clean
Sandbox acceptance remain unverified. All application, exact-source CI, native
installer and packaged-upgrade checks remain mandatory. Failed checks block
publication. A faulty release must be replaced through the signed update process;
the previous release artifacts remain available. The owner's app is not restarted.
