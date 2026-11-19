# Memory freshness and run provenance

The managed realm digest previously ignored `realm.json.env`. It combined its previous bullets
with a fresh machine probe; owner-supplied labels could therefore never arrive through a refresh.
Startup did not regenerate the digest, and frontmatter timestamps were stripped before injection.
The ordinary realm-note editor already writes `<realm>/memory/*.md`; those notes load for every
agent. Private notes load only for their owner.

The generator now overlays nonblank saved environment values on detection. Blank fields return
to detection; clearing an unprobed override removes it instead of reviving the previous digest.
`env.Notes` carries free text. UTF-8 reads are strict for realm settings and writes already use
the atomic UTF-8 writer. Bad encoding preserves both the settings and the previous digest and
returns an error rather than producing a digest from defaults.

Settings, owner, roster and goal saves regenerate the digest. Startup refreshes registered
realms; execution refreshes again before assembling chat, job, inbox and dry-run context. Paired
dry runs share one frozen context and memory receipt. Generation holds the realm lock followed
by the memory lock, including reads, to prevent an older refresh replacing a newer one.

`updated` records content changes; `refreshed` records regeneration, even with unchanged content.
Only content changes create prior-version snapshots. The refreshed time appears in the agent's
system-memory section and the Memory page. Refresh failures propagate from settings routes;
startup logs failures, and a run that cannot refresh stops before invoking its engine.

Memory receipts contain title, scope, path, timestamps and a SHA-256 of each included body.
Assembly collects them from the same reads as the prompt. The coordinator attaches the receipt
when submitting the engine request and persists it with the terminal thread reply and run report.
The receipt describes inputs supplied, not proof that a provider attended to or acted on them.
It is not a full prompt archive and is not retroactively inferred for earlier runs. The thread
sidebar is explicitly a current-context estimate, while reply/job details show recorded inputs.

Regression coverage: `tests/test_memory_freshness.py`, plus the system/core memory, execution,
access-policy, dry-run, settings, persistence, UI and golden-page suites. All fixtures are synthetic.
This source change does not itself install or publish a new application version.

Validation on 19 November 2026: the final isolated Windows suite passed **4,885 tests with six
skips**, using Python 3.12.14 and the pinned pytest 9.1.1. JavaScript syntax and diff checks passed.
The four intentionally changed golden pages were reviewed. An isolated browser fixture verified
the environment form's Unicode save, immediate digest regeneration, visible regeneration time,
and the recorded app/system/realm/private memory list beneath a reply. A read-only digest preview
against the reported settings preserved every saved environment value without changing live files.
No installed-app update, public release or packaged release validation was performed.
