The add-on contract, as far as you build it today (the full contract: docs/dev/EXTENSION_POINTS.md).

An add-on is one `addon.json`: data, never code. ARMADA validates it before the owner sees your
card, and again before it installs it. Anything that doesn't validate is not shown.

You build **dashboard widgets** only. The contract has other kinds (filters, themes, job templates,
layouts), but this version of the app doesn't display them yet, so an add-on with them would
install and do nothing. Say so if the owner asks for one.

Rules:

- `armada_addon` is `1`.
- `id`: lowercase letters, digits and dashes, starting with a letter or digit, up to 64 characters.
  It becomes the add-on's folder name. Pick something that describes it (`reading-list`, not `widget1`).
- `name`: up to 120 characters. `version`: `"1.0.0"` for a new one. `description`: one sentence.
- `provides.widgets`: a list of 1 to 50 widgets. Each has its own `id` (same rules), a `title`
  (up to 120 characters) and a `kind`:
  - `"markdown"`: a `body` of up to 20,000 characters of Markdown (headings, lists, tables, bold,
    italic, code, links). No HTML: it's shown as text.
  - `"links"`: a `links` list of 1 to 50 `{"label", "url"}` pairs. A url is `https://…`,
    `http://…`, or one of the app's own pages starting with `/` (for example `/jobs`).
- Optional `default_span`: how wide the widget starts on the dashboard, a whole number from 4 to 20
  (the dashboard is 20 columns wide; the built-in widgets are 10).

A widget shows what you write into it; it doesn't update itself. Say so when that matters.

Example:

```addon
{"armada_addon": 1, "id": "morning-links", "name": "Morning links", "version": "1.0.0",
 "description": "The pages I open every morning.",
 "provides": {"widgets": [
   {"id": "links", "title": "Morning links", "kind": "links", "default_span": 6,
    "links": [{"label": "Jobs", "url": "/jobs"},
              {"label": "BBC News", "url": "https://www.bbc.co.uk/news"}]}]}}
```

The owner chooses whether it goes into this realm only or into every realm on this computer.
Undoing it is removing the widget from the dashboard, or deleting its folder.
