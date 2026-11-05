# Windows runtime security baseline

The 0.99.124 candidate moves the Windows installer from Python 3.12.10 to
**Python 3.14.10 x64**, the maintained 3.14 binary line. The source of truth is
`armada/runtime_spec.py`: version, full security baseline, Python ABI/DLL/path
names, archive URL/hash, upstream SPDX URL/hash, and first required app installer.
Installer and signed-package builders both consume it. CI covers the pinned patch
and the current 3.14 patch. Do not change only the installer or only the manifest.

## Review and provenance

Reviewed 5 November 2026 against the official
[Python release](https://www.python.org/downloads/release/python-31410/) and
[maintenance schedule](https://peps.python.org/pep-0745/). The official archive's
SHA-256 is `90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159`.
The downloaded Python executable and DLL also carried valid Python Software
Foundation Authenticode signatures. This does not confer publisher signing on
ARMADA's own launcher or installer.

The [upstream SPDX inventory](https://www.python.org/ftp/python/3.14.10/python-3.14.10-embed-amd64.zip.spdx.json)
is pinned separately to SHA-256
`d448c78f5fae170303d3b022d61507155e4d30e541c32bff3a4edd2b1e8dbf47`
and is copied into the installer's licenses folder. Unverified downloads never
become cached build inputs; a changed cached file stops the build and preserves
the mismatching evidence. Successful cache writes use atomic replacement.

Each installer also carries `runtime-inventory.json`: the actual staged Python,
OpenSSL, SQLite and zlib versions, all pinned Python packages, runtime tag and
upstream provenance. The build refuses a staged interpreter with the wrong patch.
The observed candidate uses OpenSSL 3.5.9, SQLite 3.50.4 and zlib 1.3.1.zlib-ng.
The upstream inventory may describe components beyond the embeddable payload;
the generated local inventory describes the libraries actually queried.

The nine package pins are unchanged. Public PyPI version metadata reported no
advisories for those pins on the review date. That is a dated metadata check,
not a guarantee that all vulnerabilities are known. Python.NET and WebView2
imports and the compiled launcher/native tray preflight passed on the candidate.

## Upgrade contract

Runtime tags include the **full Python patch**, pinned packages and bootstrap
protocol. A patch change requires a full installer: package updates only replace
`armada/` and cannot repair a vulnerable interpreter. This intentionally prefers
an explicit installer requirement over silently treating an old patch as current.
Build-host Python does not affect the release's advertised requirement.

Versions before 0.99.124 see a different signed runtime tag, show the existing
installer-required state, and do not download or stage the incompatible package.
Finish active work, quit ARMADA, and run the installer over the existing install.
The installer replaces application/runtime folders; realms and owner settings
remain outside those folders. Later compatible package updates use the normal
signed update and recovery path. A subsequent baseline change must also advance
`INSTALLER_BASELINE_VERSION` and the owner-facing upgrade instructions.

The release probe now exercises the previous signed client with its old runtime
tag before the compatible update rehearsal. It verifies installer-required state,
no package download/staging, unchanged installed code and a synthetic pending-work
record. It restores the staged marker even on failure. This probe runs the previous
client under the new staged interpreter; it does not claim to execute the full
installer or test an old interpreter. An isolated preserved old runtime can supply
additional migration evidence.

## Required evidence and acceptance limits

1. Targeted signed-manifest/tag tests, mismatching cache/download refusal and
   old-runtime versus matching-runtime staging behavior.
2. Full pinned isolated gate and exact-source Windows CI on the new runtime.
3. Packaged launcher interruption recovery, WebView2 sessions, tray and all restart
   cases; signed previous-client boundary and compatible upgrade checks.
4. Clean-machine installer rehearsal, with its actual result and installer hash.
   The existing unsigned-maintenance exception remains explicit if Windows blocks
   execution. Neither signing nor clean-machine acceptance is inferred from local
   success. See [the release procedure](RELEASING.md).

The full installer still force-stops processes under its own chosen installation
directory. Users must finish work and quit first. A cooperative full-installer
handover remains separate from the compatible updater's drain/recovery contract.
No owner application is restarted or installed over for development validation.
