# 0.99.129 — Native view recovery without replaying work

M7 candidate, 6 November 2026. Publication and maintainer acceptance are pending.

The Windows Form now owns bounded renderer/browser recovery independently of
server execution. Failed controls are disposed and replaced inside the same HWND.
Authentication, safe display route and realm are checked before returning to the
page. Repeated failures stop automatic retries and expose native restore/close
controls. Bounded native script tasks replace per-call waiting threads.

Unsent chat and Alexander text has a bounded native copy, because a fresh browser
storage write can be lost when its process exits. Composer identity checks prevent
cross-realm/page restoration. Sending clears the copy; uncertain Alexander request
delivery is cancelled across view generations, never automatically repeated.
See [the complete recovery contract](DESKTOP_PRESENTATION_RECOVERY.md).

## Validation

- Focused desktop/companion/thread suite: **121 passed** before the final two
  event-generation/quit regression tests were added.
- Real native failure injection: **86 checks passed**, including renderer crash,
  infinite JavaScript loop, shared browser-process loss, retry exhaustion/manual
  recovery, drafts, unchanged server/auth/HWND and exactly one in-flight synthetic
  request completion. Busy restart then verified browser/Form/tray teardown.
- Native panel captures reviewed in light and dark, for the main window and a
  400 × 500 companion. Production JavaScript syntax checks pass.
- Detached-thread native probe: **79 checks passed**, with no browser bridge
  errors after gating draft messages on the installed native recovery channel.
- Initial full run: 4,162 passed / six skipped / four failures. Corrections add
  native error-category diagnostics, recognize the existing instance route in the
  documentation checker, clarify a historical line-number reference and supply
  the browser URL API in the Node fixture. Targeted follow-up: **323 passed**.
- Corrected full pinned isolated gate: **4,166 passed, six skipped** in 634.23s;
  repeated with the final probe correction: **4,166 / six skipped** in 642.07s.
  Generated references are current; both changed golden pages were reviewed.
  Exact-source Windows CI, signed-upgrade gate and public verification
  remain pending.
- The first packaged run stopped at the lost-acknowledgement probe: it still
  intercepted direct `evaluate_js` calls, which are now behind the bounded-call
  interface. Injection at the production call interface passed all **16 session
  checks**, still requiring one delivery after two acknowledgements. Application
  bytes are unchanged by this probe correction. The repeated complete packaged
  preflight passed all five launcher recovery interruption points, clean/legacy
  DLL isolation, **16** WebView2 session checks, **68** tray checks, **69** teardown
  checks in each of visible/tray/busy restart modes, and **86** presentation checks.
- The owner app has not been restarted. Tests use isolated synthetic profiles;
  no live realm, connector or provider execution is used.
- Release model preferences are unchanged. Connected-provider/catalogue filtering
  and unknown-model provider-default fallback remain authoritative.

## Boundaries

This does not establish the historical ghost surface's root cause or guarantee
recovery from Windows compositor, graphics-driver or native UI message-loop hangs.
It does not reset the compositor, kill unrelated processes, restore attachments or
recover drafts not delivered before the crash. It does not preserve every transient
UI state. Native copies survive browser loss, not application/OS termination.

Bundled Python 3.14.10, baseline installer 0.99.125 and launcher protocol 2 are
unchanged. The installer adds a mandatory presentation fault probe; runtime and
launcher dependencies are unchanged. The existing unsigned maintenance beta and
clean-machine WebView2 acceptance limitations remain open. No trusted Windows
publisher or clean-machine GUI acceptance claim is made. Update assets still
require Ed25519 signing and the enforced release procedure.

## Release decision

Any failed required gate blocks publication. Retain 0.99.128 as the preceding
known release; the normal signed-update bootstrap retains its recovery/rollback
contract. A new startup/authentication failure or repeated view-recovery loop is
a reason to stop rollout and investigate, not to replay work or overwrite realms.
There is no data migration in this release. Do not restart the owner's app as a
release smoke test.
