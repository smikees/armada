"""A self-contained error screen: no realm/config reads, scripts or authenticated assets."""
from html import escape


def page(status, reference, message=""):
    title, explanation = {
        401: ("Reopen ARMADA to continue", "Open ARMADA to access this local session."),
        409: ("The selected realm changed", "Return to ARMADA to load the current realm, then try again."),
        400: ("This page could not be opened", "Return to ARMADA and open the page again."),
        500: ("This page could not load", "Try again. If it still fails, return to ARMADA and use the diagnostic reference below."),
    }.get(status, ("This page could not load", "Return to ARMADA and try again."))
    if status == 409 and message:
        explanation = message + " Return to ARMADA to load the current realm."
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} | ARMADA</title><style>
:root{{color-scheme:light dark;font-family:system-ui,sans-serif;background:#f7f5f1;color:#292d29}}
body{{margin:0;min-height:100vh;display:grid;place-items:center}}
main{{box-sizing:border-box;max-width:600px;padding:40px;margin:24px;border:1px solid #d5d6cd;border-radius:20px;background:#fff}}
.brand{{font-size:14px;font-weight:750;letter-spacing:.18em;color:#687254}}
h1{{font-size:28px;line-height:1.2;margin-top:28px}}p{{line-height:1.65}}
.actions{{display:flex;gap:12px;flex-wrap:wrap;margin:28px 0}}
a{{display:inline-block;border-radius:9px;padding:11px 16px;background:#586947;color:#fff;text-decoration:none;font-weight:600}}
a.secondary{{background:transparent;color:inherit;border:1px solid #999}}
a:focus-visible{{outline:3px solid #9aae7f;outline-offset:3px}}
small{{display:block;line-height:1.7;color:#646a62}}code{{user-select:all;overflow-wrap:anywhere}}
@media(prefers-color-scheme:dark){{:root{{background:#171b18;color:#edf0e8}}main{{background:#252b26;border-color:#495346}}.brand,small{{color:#b7c5a6}}}}
</style></head><body><main data-armada-recovery="{status}">
<div class="brand">ARMADA</div><h1>{escape(title)}</h1><p>{escape(explanation)}</p>
<div class="actions"><a href="">Try again</a><a class="secondary" href="/">Return to ARMADA</a></div>
<small>Diagnostic reference: <code>{escape(reference)}</code><br>
Find this reference in <code>%USERPROFILE%\\.armada\\logs\\armada.log</code>.
Nothing has been sent.</small></main></body></html>"""
