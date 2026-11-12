# 0.99.143 - Monitor recovery, saved detached threads and Activity monitor

Released on 12 November 2026 from `90a0897be9fe9f50c3127512fef63e845654029c`.
The [GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.143)
and [website](https://armada.stamih.com/) both offer v0.99.143.

Unreachable visible windows move onto a surviving monitor after Windows reports a
display change. The tray's **Bring all windows here** gathers the cockpit and
companions on the cursor's display, including when a KVM preserves EDID and Windows
continues to register the other monitor. Native recovery compares physical bounds
with working areas, and its UI callbacks never wait for the window-creation lock.

Detached threads retain their realm and reopen in a 20-pixel cascade after a full
quit or restart. Closing one removes it from the saved session. Their headers use
the standard model badge and agent marks, without the redundant main-thread label.
Background restored views preserve unread state until focused.

The new **Activity monitor** dashboard widget groups working agents, unread replies,
input requests and failed replies, with attention items moved inside it. Local
four-second refreshes preserve focus, scrolling and disclosure state, pause while
hidden and leave unread metadata untouched. The widget supports existing layout,
hide/show, resizing and section promotion controls. See [the desktop/session
contract](WINDOW_SESSIONS.md).

The final enforced publisher passed **4,483 tests with six skips** in 864.91 seconds.
Both exact-commit Windows jobs passed **4,485 tests with four skips**, without a
retry. The publisher verified the explicit manual selector and recorded its real
trigger in `build/release-evidence-0.99.143.json`.
[Windows CI](https://github.com/smikees/armada/actions/runs/43237995694).

Final-source stabilization passed in **262.12 seconds**, including three
**124-check** native window cycles, six page-work checks and 20 owner-workflow
checks. Evidence is in `build/stabilization-20261112-153122-735117`.
The freshly bundled Python 3.14.10 runtime separately passed all **124 native
thread checks** in `build/window-improvements-bundled-0.99.143.json`.
Light/dark dashboard captures, narrow detached headers and 150-percent layouts
were reviewed. Actual hardware KVM switching and mixed-DPI display removal remain
unverified; the probes use synthetic bounds and do not change monitor configuration.

The final installer passed all five launcher recovery points, external DLL
isolation, 16 WebView2 session checks, 69 tray checks, three 70-check restart cases
and 87 presentation checks. The signed upgrade from v0.99.142 passed **72 checks**
against these assets.

Public verification confirmed the update signature, tag/manifest commit, ZIP hash,
all **491 packaged source files**, website links and the downloaded installer hash.
The **23,415,713-byte** installer has SHA-256
`c582b4fc7ac6499c4c4bc1240223108d6f6d97435d967d060f7f93b7e4b11774`.
The update ZIP has SHA-256
`bb753c6024327fa2ca54fad0abdd6920f16fb3a1fde705bd9af1e88f3018e539`.
Evidence: `build/public-release-0.99.143.json`, `build/upgrade-0.99.143.json` and
`build/release-evidence-0.99.143.json`.

This continues the owner-authorized unsigned maintenance beta distribution.
Ed25519 update signing passed; trusted Windows publisher signing and clean-machine
Sandbox acceptance remain unverified. The owner app was not restarted, live realms
were not modified and the temporary worker account was left in place as requested.
