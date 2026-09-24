# `armada/icons.py`

Icon subsystem — the single source of every SVG the UI draws.

`ICONS` maps a name to an SVG body (path/group, no wrapper). `_icon()` wraps a body in a sized
<svg> for server-rendered HTML; `_ICONS_JS` emits the same registry to the browser so client JS
(`window.mcIcon`) renders from the SAME definitions (no hand-kept blobs that drift). Bodies are
inlined from Lucide (design's set) + a few from Iconify/simple-icons/carbon/hugeicons/phosphor.

Also here: filename→icon mapping (`_file_icon`), the realm-icon picker (`_realm_icon`), and the
list of Lucide names offered as realm icons (`_REALM_ICON_NAMES`).

### `_file_icon(name: str)`

Icon key for a filename, chosen by extension (pdf/doc/sheet/code/image → generic 'file').

### `_icon(name: str, size: int=18, style: str='')`

—

### `_realm_icon(realm, size: int=15)`

Realm icon: an uploaded image if present, else a monochrome Lucide icon, else legacy emoji.
