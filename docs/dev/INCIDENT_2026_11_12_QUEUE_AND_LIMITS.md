# Owner chat queued at the critical-job reserve; session rows clipped

The owner reported Marcus waiting for execution capacity with Fable 5.2 while the
same model worked in Claude. The installed v0.99.144 run-policy and UI assets matched
the source. The local Claude reading was 93% session use and 40% weekly use; the
realm had approved critical Claude jobs and no explicit threshold override.

The default 80% critical-job reserve applied to every noncritical ticket, including
owner chats. It could hold a chat before any provider call, even with no running
executions. The generic waiting message concealed the difference between this
voluntary reserve, local concurrency and an actual provider refusal. Historical
stopped Marcus turns show cancellation before execution; the exact historical
ticket snapshot was no longer present when inspected. The 93% state was reproduced
with synthetic approval and usage records, without making a provider call.

Admission now carries an explicit background flag. Chat and owner dry-run tickets
do not acquire a usage deferral. Scheduled work, Inbox tasks, command jobs and
maintenance wrappers retain background admission; nested model calls inherit the
parent's classification. Critical priority, the protected local slot, conversation
FIFO, kernel ownership and API accounting remain enforced. Background quota
deferral requires an available, fresh, finite reading and a reset in the future.
Expired, future-dated and unreported windows cannot impose a quota wait.

The same predicate now decides eligibility and describes the queue blocker.
Changing reasons update the original saved turn and shared thread snapshot, so
main and detached views show the same explanation. Stop still cancels queued work;
releasing a blocker continues the original invocation without replaying a request.
No extra API grant, automatic business-tool replay or provider-limit bypass was
introduced.

The owner also reported missing dashed session bars for weekly-only Codex and
Gemini data. Their HTML existed, but a Claude API-credit span occupied an implicit
third grid row. Other provider grids stretched to that column's height, moving
their second rows below the fixed header's overflow clip. The old native test
used all-unavailable payloads without API credit, and checked element dimensions
without checking their intersection with the clipping container. It missed this
real combination.

Credit and the Codex bucket selector now occupy the existing title line, outside
the two-row provider grids. Provider grids align their contents to the top. Native
coverage uses 93%/40% Claude readings, weekly-only Codex/Gemini, API credit and
multiple Codex buckets in light and dark Armada II. It asserts every row and the
credit are inside the visible header, rather than merely present in the DOM.

Focused validation passed 158 isolated queue, accounting, fallback, question and
usage tests. The native owner journey passed 33 checks. Its captures are
`build/m11-mixed-limits-armada-ii.png` and
`build/m11-mixed-limits-armada-ii-dark.png`; the report is
`build/queue-limits-native-final.json`. Final-source release evidence is recorded
separately after the complete publisher and stability gates.

Diagnostics read only scheduling metadata, usage readings, installed asset hashes
and the Overview's limits-related styles. No credentials, conversation text or
business outputs were copied. The owner app was not restarted, and no live job,
realm or worker account was changed.
