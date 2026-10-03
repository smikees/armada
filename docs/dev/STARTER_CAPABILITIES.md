# Starter capabilities — setup CX, 2026-09-28

Setup and Capabilities > User now render the same capability card. Risk is calculated by the
same policy, from the same catalogue inspection fields; origin, publisher, source link,
Runs and Can touch are preserved when a selection is saved in realm.json.toolkit.
Skills download through the normal catalogue path and are enabled. Optional MCP selections
are added disabled with their connection guide: catalogue membership is not authentication.

## Recommended shortlist

| Capability | Publisher / source | Initial choice | Reason |
|---|---|---|---|
| Word, Excel/CSV, PowerPoint, PDF | Anthropic skills | Selected | Everyday document work |
| Writing partner | Anthropic skills | Selected | Proposals, briefs and structured drafting |
| Second look | Anthropic skills | Selected | Challenge assumptions and check advice |
| Updates and reports | Anthropic skills | Selected for Company | Routine organisational communication |
| Themes, posters and visuals | Anthropic skills | Optional | Useful when producing designed documents |
| Google Drive, Gmail and Calendar | Taylor Wilsdon / Workspace MCP (community) | Optional, setup required | One connection for documents, email and scheduling |
| Windows MCP | CursorTouch (community) | Optional, setup required | Desktop apps and computer operation |

## Google connector evaluation

User chose evaluation of a community connector over Google's Developer Preview remote servers.
Upstream documentation and launch code reviewed on 2026-09-28:

- [Workspace MCP](https://github.com/taylorwilsdon/google_workspace_mcp) exposes standard MCP,
  documents Claude Code and Codex usage, and has service selection plus read-only mode.
  Recommendation: trial it with `--tools gmail drive calendar --read-only --tool-tier core`.
  Its [quick start](https://workspacemcp.com/quick-start) still requires a Google Cloud project,
  enabled APIs and the user's OAuth client. Browser consent follows that preparation. This is
  simpler than Google's preview enrolment, but is not a one-click account connector.
- [Aaron's Google Workspace MCP](https://github.com/aaronsb/google-workspace-mcp) also needs a
  Google OAuth client. Its desktop bundle does not remove that prerequisite for CLI users.
- [Google's own servers](https://developers.google.com/workspace/guides/configure-mcp-servers)
  require Workspace Developer Preview membership and Cloud/OAuth setup at review time.

Prefer the first candidate for a bounded Windows integration trial because it explicitly
supports a small, read-only service set. This is a documentation/source evaluation, not a
completed security audit or a live OAuth verification. Neither credentials nor Google data
were accessed during this work.

[Windows MCP](https://github.com/CursorTouch/Windows-MCP) documents both CLI clients and
`uvx windows-mcp serve`. It can operate the desktop and run terminal commands, so the shared
risk policy shows High risk. It is a separate optional installation, not an Armada dependency.

## Remaining connector delivery work (before claiming one-click enablement)

1. Pin/test Windows package versions and own their install/process lifecycle.
2. Register the MCP server separately with each connected CLI, preserving existing config.
3. Provide Google OAuth-client entry and browser consent without putting secrets in realm files.
4. Verify the requested read-only service/tool set and actual connected state for each provider.
5. Exercise disconnect, cancellation, retries and switching providers in an isolated profile.

Until that delivery passes, setup says **Setup required**, links to the publisher's guide,
and saves the entry disabled under Capabilities > User. It does not promise a working connection.

## CX validation

Browser walkthrough uses a separate profile and mocked provider status, without paid model
turns. Cover splash → numbered Welcome, dependency labels, name gating, two-way drag including
custom drafts, live counts, gallery selection, read-only profile, outside-click dismissal,
team creation and shared capability rendering. Backend regressions cover downloaded/enabled
skills, persisted disabled connectors with provenance, retries and avatar validation.

Validation result: 2,558 passed / 2 skipped. Browser confirmed mouse navigation into Welcome,
step numbering, two-way drag and counts, custom gallery profile, outside-click dismissal,
team creation, capability disclosures, saved skills and disabled Google connection under User.
The Enter shortcut now ignores summary/selection controls instead of triggering Add.

Refreshed isolated package: `build/setup-cx-hndhf382/bundle/ARMADA-CX-Setup.exe`.
Embedded Python smoke passed; installer compiled. SHA256:
`f9b875f4dac86f207e8b5fdf3159e0c143c00b53ec4924361b681f0a654007f6`.
Native test window runs PID 19644, sharing the prior isolated setup profile; the normal
installation and live realms were not restarted or changed. Packaged Check displayed Claude
2.1.283 signed out, Codex 0.157.1 signed in, Python 3.12.10 and WebView2 153.0.4234.48.
Sandbox installer execution and real connector OAuth remain unverified.
