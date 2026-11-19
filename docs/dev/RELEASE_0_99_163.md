# v0.99.163 — fresh memory and readable agent questions

Prepared on 19 November 2026. Final release gates and publication are pending.

System memory now honors saved Environment settings and free-text notes. Saves,
startup and run preparation regenerate the digest; agents see its regeneration
time. New replies and job results retain the exact memory inventory supplied to
that run. UTF-8 settings are read strictly, with errors preserving existing data.
See [memory freshness and provenance](MEMORY_FRESHNESS.md) for the storage and
failure boundaries. Receipts describe supplied context, not proof of attention.

Identical provider reply/error messages are displayed once. Distinct errors,
partial replies and interruption details are preserved. Agent questions use the
shared safe Markdown renderer, so paragraphs, line breaks, lists, emphasis and
code render consistently in the live panel and saved conversation. Body text is
normal weight. Question IDs, answer choices and delivery semantics are unchanged.
Raw HTML is escaped and unsafe link schemes remain inert.

The release retains runtime compatibility and the standing unsigned maintenance
beta boundary. Update packages are Ed25519-signed; Windows publisher signing and
clean Sandbox acceptance are not claimed. The owner requested both publication
and updating the installed app. The installed update will use the authenticated
in-app path after active work has finished.

Python's official Windows release list was checked on 19 November 2026:
[3.14.10](https://www.python.org/downloads/windows/) remains the current patch in
the supported 3.14 branch. The packaged runtime is unchanged. Provider preference
availability is checked with provider metadata before publication.

Final validation and publication evidence will be recorded after the gates pass.
