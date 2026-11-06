# Desktop presentation recovery

M7, released in 0.99.129. The Windows Form owns a presentation controller; the
local server, execution coordinator and scheduler retain their existing ownership.
Replacing a failed view never relaunches an engine or resubmits a request.

## Failure and recovery

`desktop_recovery.Presentation` handles main renderer exit/unresponsiveness and
browser-process exit. It subscribes to both Core and Environment events, deduplicates
recovery, and ignores events from withdrawn controls. A two-second page heartbeat
also detects a renderer that has stopped answering for twelve seconds. GPU and
subframe events are logged without replacing the entire view. Microsoft documents
these distinctions in [WebView2 process events](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/process-related-events).

Recovery retains the Form/HWND and protected browser profile, removes and disposes
the old WebView2 control, and creates one replacement. It loads only an allowlisted
display route through the local authentication bootstrap. API/action, content-file,
external and credential-bearing origins are not recovery destinations. The last
observed realm stays in `_realm`; recovery does not switch the server's active realm.
The bootstrap's validated destination is retained before the first heartbeat, so
an immediately failing companion does not recover to the cockpit.

An authenticated `/api/instance` response must match the running owner's nonce and
application version before the native recovery panel disappears. Recovery has a
25-second deadline and a limit of two automatic attempts per rolling 120 seconds.
After that, native **Restore view** and **Close window** controls remain available.
Close retains normal main-window tray behavior; tray Quit still performs full quit.
Suspend/resume time does not consume a pending heartbeat or recovery deadline.

## Bounded calls and drafts

`desktop_operations.ScriptCalls` keeps at most four native script tasks per Form.
Deadlines include UI queueing and a stalled native start. Calls that expire while
queued never execute. Started calls retain their capacity until completion or
control disposal. Reset fails waiters and discards late completions; it does not
spawn replacement threads. Quit disables recovery while allowing the bounded final
state snapshot to finish before disposing the Form.

Unsent chat and Alexander text uses browser storage plus two bounded in-memory
native slots per window (65,536 and 6,000 characters). Only first-party display
documents can deliver these draft messages. Exact realm/page composer keys gate
restoration; passwords and arbitrary form fields are not captured. Sending clears
the native slot as well as browser storage. Native copies are cleared on close.
They survive a browser-process crash, not an application/OS crash; text not yet
delivered to the native process can still be lost. Attachments are not restored.

Adding `_realm` to a recovered route does not change a chat draft's identity.
Existing draft keys migrate on read. A pending Alexander delivery is cancelled
when the presentation generation changes: a lost acknowledgement never causes
automatic resubmission into the replacement renderer. Existing server-owned work
and saved transcripts remain authoritative.

## Evidence and limits

`tools/presentation_probe.py` uses hidden native windows, synthetic HTTP data and
an isolated profile. It crashes its own renderer, executes an infinite JavaScript
loop and kills only the WebView2 browser belonging to that profile. It checks
same HWND/server/auth identity, disposal of old controls, bounded calls, draft
restoration, retry exhaustion/manual recovery, companion recovery and exactly one
completion of an in-flight synthetic POST. The existing tray/busy-restart harness
then checks native disposal, vanished HWND and browser/tray shutdown. Installer
staging requires this probe and retains `build/presentation-recovery-staged.json`.

This is renderer/browser recovery, not a guarantee against a hung native message
loop, Windows compositor or graphics driver. The earlier owner-visible ghost
surface disappeared after a compositor restart; its historical cause has not been
conclusively reproduced. The app does not reset the compositor or kill unrelated
processes. Recovery preserves unsent composer text, not every transient UI state.
Maintainer acceptance, publisher signing and clean-machine WebView2 acceptance
remain separate gates.
