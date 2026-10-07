# ARMADA 0.99.86 verification

Settings → App → Appearance → Fonts gains a reference size beside the two font
family controls, using the shared dropdown. The default 13 px preserves the
existing typography. Whole-pixel choices from 10 through 26 scale headings,
labels, code and message text proportionally while retaining image/icon sizes
and panel dimensions. Settings selection previews; Save persists and Cancel
reloads the saved choice.

Ctrl+ (including Ctrl=), Ctrl− and Ctrl0 adjust by one reference pixel or restore
13 px. Numpad variants and repeated key presses are supported. Shortcuts persist
only the size, preserving other unsaved appearance choices and conversation
drafts. Writes are serialized and coalesced while in flight. A failed save retains
its exact reason and restores the persisted size. Bounds and malformed values
are validated on both sides. The authenticated preference endpoint also works
before realm creation and while viewing an archived realm.

The shared first-party controller makes absolute CSS, inline and SVG text sizes
relative to one CSS variable, including dynamically streamed text. Relative
sizes inherit scaling once. SVG presentation attributes retain normal stylesheet
precedence. Only newly added/changed typography is observed after initialization;
no background service or runtime dependency is added. BroadcastChannel updates
other app windows; a focus refresh reconciles missed changes without overwriting
an unsaved preview or a newer local save. WebView2's native zoom control is
disabled so page zoom does not compete with the reference shortcuts; text editing
shortcuts remain intact.
[Microsoft's WebView2 setting](https://learn.microsoft.com/en-us/microsoft-edge/webview2/reference/win32/icorewebview2settings)
documents this behavior.

Regression checks cover validated persistence, defaults, exact write failures,
authentication/origin guards and realm-independent preferences. Browser controller
tests cover repeats/coalescing, bounds, reset, editable-field drafts, unsaved
preview baselines, stale focus responses and companion updates. A hidden real
Windows app test verifies computed stylesheet/inline/SVG sizes, SVG precedence
and attribute updates, fixed icon size, preserved drafts, production shortcut
handling, navigation, Settings selection and Alexander synchronization. These
checks also run in the mandatory signed-package upgrade gate.

The existing unsigned beta publisher-signing and clean-Sandbox acceptance
boundaries remain; this release does not claim to resolve them. Exact release
evidence is retained under `build/`.
