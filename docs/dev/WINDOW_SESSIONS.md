# Monitor recovery, detached sessions and Activity monitor

Native bounds and Screen.WorkingArea are compared in physical pixels. Display-change
notifications request a UI-thread recovery check; a two-second timer is the fallback.
An adequate portion of the title/drag area must remain visible on a working area.
Recovery fits unreachable visible windows to the nearest surviving display. Hidden
and minimized windows stay hidden/minimized; restoring the cockpit checks its bounds.
Small working areas can lower the native minimum size so the recovered window fits.
The tray's Bring all windows here action explicitly gathers windows on the cursor's
display. This also covers KVMs that preserve EDID and produce no disconnect event.
Timers and the static display-event subscription are released during desktop teardown.

`desktop-threads.json` is owner-local session state outside realms. It stores only
realm paths, agent IDs and thread IDs, without URLs, credentials or transcripts.
Opening/closing a window updates the locked atomic snapshot. Whole-app shutdown
retains it; individual close removes that window. After authenticated startup,
existing threads are validated and reopened without switching the cockpit's realm.
They use a 20-pixel cascade from the companion anchor. Unavailable entries are skipped.
The restore loop reads its complete snapshot before opening windows can rewrite it.

Detached headers share the standard model badge and coordinator, inspector and
autonomy marks. The redundant main/sub-thread label is omitted in that view. Reading
is acknowledged through an authenticated realm-bound action after focus, rather
than by rendering a background window. Companion access remains realm-bound.

The Activity monitor is a built-in dashboard widget (`activity`), including normal
layout persistence, hide/show, resizing and promotion to a section. Independent
groups preserve simultaneous working, unread and input signals. Latest failed chat
outcomes remain until superseded. Existing attention items appear inside the widget.
Four-second refreshes use local records only and pause when the document is hidden.
They preserve scrolling, attention disclosure state and keyboard focus. Failed
refreshes show that the current reading is stale; merely viewing the widget does
not change unread metadata.

Synthetic native checks cover real offscreen WinForms recovery, cross-realm session
reconstruction and its 20-pixel cascade, tray recovery and desktop teardown. The
dashboard probe exercises working/unread transitions and light/dark responsive
layouts. Actual hardware KVM switching and mixed-DPI monitor removal still require
owner validation; no physical monitor configuration is changed by these probes.
