# 0.99.139 — Longer chats and settings polish

Released from `0352fe0458e6de5c8045591028d42bcbec3a4367` on 10 November 2026.
The [GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.139)
and [website](https://armada.stamih.com/) both offer v0.99.139.

ARMADA no longer ends a chat reply after 20 minutes. Stop still cancels active
work, and jobs and Inbox tasks use their configured time limits. The thread rail
keeps its disclosure state during refreshes. App Settings and Memory → App share
a read-only system memory reader and reveal the file that supplies the content.
Existing saved instructions are displayed from their original source. The engine
switches control access for new ARMADA calls while preserving CLI sign-in.

The publisher passed **4,400 tests with six skips** on Python 3.14.7. Both
[Windows CI jobs](https://github.com/smikees/armada/actions/runs/42836705780)
passed **4,402 tests with four skips**, including the packaged Python 3.14.10
matrix entry. The clean release commit passed the native stability gate in
231.42 seconds with three 100-check thread-window cycles. The native memory and
Inbox probe passed 11 checks covering both readers, file reveal, and the owner
timing override. Evidence is in `build/stabilization-20261110-154236-970592` and
`build/inbox-timing-0.99.139.json`.

The staged installer passed launcher recovery, session, tray, restart, and
renderer recovery checks. The light and dark recovery views were reviewed in the
main and companion windows. The upgrade from v0.99.138 passed **72 checks**.
The installer uses the existing unsigned beta distribution with Ed25519-signed
updates. Windows publisher signing and clean-machine Sandbox acceptance are
still open for the beta.

The public HTTPS page displays the matching version, release notes, and installer
link. The downloaded installer matched the release build. The latest update
manifest signature and package hash verified, and all 24 changed package files
matched the release checkout. Installer SHA-256 is
`984ad0fdd21d1c20481cddc98806f3e1e1250360e1050baee310ac055648fd66`.
