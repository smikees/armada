# ARMADA 0.99.78 release verification

Maintenance fix for ARMADA closing without reopening after Restart to update on
a machine whose realm folder contains spaces.

## Cause and fix

Reproduced on native Windows: Python os.execv calls CRT _wexecv, which joins argv
without quoting its elements. A realm such as `D:\ARMADA\Owner's projects` was
passed to the successor as two arguments. Its CLI rejected the extra argument
and exited. An installation path containing spaces could also break the bootstrap
script path. The development machine's realm path contains no spaces.

Both the app restart and scheduler re-exec now use a shared replacement helper.
On Windows it quotes each argument using subprocess.list2cmdline before os.execv;
POSIX receives the original argument list. Explorer-owned desktop startup and
the stable update bootstrap remain unchanged. No shell is involved.

The first update from an affected older version still invokes the old restart
code. If ARMADA closes and does not reopen, launching it manually completes the
transition; later restarts use the fix. No realm rename is required.

## Verification

- Native process tests exercise the actual app and scheduler restart entry points
  with spaces in the installation and realm paths, apostrophes and Unicode.
- Native replacement tests cover empty arguments, embedded quotes and trailing
  backslashes. A separate test preserves raw POSIX arguments.
- Focused restart, desktop lifetime, bootstrap recovery and updater tests passed.
- Full isolated suite, Windows CI and packaging validation: pending.
- No live user realm, scheduled job or global CLI policy was modified.

## Distribution

The runtime and stable bootstrap are unchanged, allowing the existing signed
package-update mechanism. The Windows installer remains an unsigned beta under
the owner's existing no-fee maintenance distribution. Authenticode signing and
clean-Sandbox GUI acceptance remain unverified; this release does not address
Application Control error 4551 or the earlier WebView2 prerequisite failure.
Standard public release gates remain unchanged and are not represented as passed.
