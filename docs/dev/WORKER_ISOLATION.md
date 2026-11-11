# Windows worker isolation

**Decision:** dedicated non-admin Windows account, accepted 11 November 2026.
API fallback requires this boundary. Ordinary operation without a configured worker
continues to use the owner's identity, as previous releases did.

The owner app holds provider keys, monthly accounting, approval seals, local HTTP
authentication and notification credentials outside every realm. The Anthropic key
is protected with owner-bound DPAPI. A budget-checking gateway keeps it in the host;
the CLI receives an invocation token. Provider errors never echo credentials.

Normal model, shell, sign-in, connector-discovery and local MCP processes run as a
dedicated local user belonging only to Users. Its password is random, non-expiring,
not changeable by that user and DPAPI-protected in the owner's control folder. No
credential is passed on a command line. The account has a private profile and its own
provider logins. Owner environment variables are allowlisted; owner secrets, proxy
configuration and provider-home overrides do not cross the launch boundary.

The owner elevates setup. A fixed, owner-controlled task creates a uniquely named
noninteractive window station with `CWF_CREATE_ONLY` and holds its Agent and Draft
desktops open. It offers no listener, launch endpoint or credential access. Existing
stations, the active desktop and shared ancestor ACLs are not changed. Browser sign-in
uses validated authorization URLs and a worker-side pseudoconsole. Setup currently
requires elevation as the signed-in owner; alternate-administrator setup is unsupported.

Owner credential/control folders deny the worker. Application/runtime code and fixed
task helpers explicitly deny worker writes. Runtime inputs are created with an atomic
owner-private descriptor, verified through held no-delete handles and shared only
when execution starts. Parent handles block redirection; ACL grants use the held
object and refuse arbitrary paths. Selected realm/workspace folders receive explicit access. Activation
checks directory replacement rights and rejects writable ancestors of trusted app,
interpreter, worker-helper or control locations. The normal per-user installation is
supported; a replaceable development checkout cannot activate the boundary. Losing
the worker manifest while an API key exists blocks execution rather than restoring
the owner identity. Setup becomes ready only after its real identity/DPAPI probe passes.

Windows children start suspended, enter kill-on-close Job Objects, then resume.
Creation thread handles are retained across account boundaries. Cancellation closes
the whole tree. Preflight/login subprocesses also own their trees. Read-denied child
handles cannot prevent Job termination and zero-active-process verification.

Approved draft scripts retain the existing LPAC AppContainer: private staged input,
restricted output, no network and no child processes. Their base Windows user remains
the owner, but their restricted token cannot decrypt owner DPAPI data or read owner
control files/process memory. They start explicitly on the private Draft desktop;
they do not inherit the owner's clipboard station. No unrestricted agent code runs
under the owner identity. Owner-requested vendor installation and desktop notification
helpers remain trusted application operations.

Agents sharing the worker account are not isolated from each other. Standard Windows
permissions can expose ordinary machine files beyond explicit shared folders. This
boundary protects owner credentials and authoritative controls; scoped tool policy
still determines each agent's intended file/service access.

CLI shell scrubbing is tested against the installed executable, not inferred from a
version string. Native PowerShell is used for Claude worker shells. POSIX runtimes may
need a worker-compatible installation. API spending is checked before every paid
request with conservative text bounds; inline media and unbounded provider features
are refused. Independently metered usage prevents understated CLI totals from reducing
the monthly charge. Missing costs retain the full reservation.

## Repeatable checks

Use an owner-protected controller and control folder, with a separate synthetic
workspace. Never point these probes at live business jobs or provide a real API key.

- `tools/worker_boundary_probe.py --setup --controller <protected public-code copy>
  --data <protected synthetic controls> --fixture <synthetic workspace parent>
  --lpac --output build/worker-boundary.json`: actual distinct SID, DPAPI/read/write
  denial, environment isolation, child identity and Stop cleanup; LPAC additionally
  checks a real protected fixture, private station, owner process and clipboard denial.
- `tools/provider_lane_probe.py --output build/provider-lane.json`: installed Claude
  CLI, fake local provider, no paid requests; verifies shell credential scrubbing and
  that the real synthetic key never enters the CLI environment.
- `tools/long_run_probe.py`: actual scheduled/Inbox paths with streaming synthetic CLI
  processes, 2,700 seconds without a ceiling and a separate 600-second explicit limit.
- The release suite, native thread-window probe, stabilization gate and packaged
  installer/upgrade gates remain required.

The fixed Windows task does not require a batch-logon grant for the worker. An
experimental Session 0 task was not used: this machine denied batch logon. No such
right was added. WSL alone was rejected as a security boundary; its normal Windows
interop and user-owned VM configuration do not isolate the owner credential store.
