"""Real capability scan/reconcile logic (offline — no CLI calls)."""
from armada import capscan


def test_norm_plugin_is_shape_tolerant():
    d = capscan._norm_plugin({"name": "a", "installedVersion": "1.2", "availableVersion": "1.3"})
    assert d["version"] == "1.2" and d["latest"] == "1.3"


def test_reconcile_sets_real_version_and_update():
    tk = {"plugins": [{"id": "brightdata", "name": "Bright Data"}]}
    changed = capscan.reconcile(tk, [{"name": "brightdata", "version": "2.1.0",
                                      "latest": "2.2.0", "marketplace": "bd"}], [])
    it = tk["plugins"][0]
    assert changed and it["version"] == "2.1.0" and it["latest"] == "2.2.0" and it.get("update_info")


def test_reconcile_clears_latest_when_current():
    tk = {"plugins": [{"id": "x", "name": "x", "version": "1.0.0", "latest": "1.1.0", "update_info": "old"}]}
    capscan.reconcile(tk, [{"name": "x", "version": "1.1.0", "latest": "1.1.0", "marketplace": ""}], [])
    assert "latest" not in tk["plugins"][0] and "update_info" not in tk["plugins"][0]


def test_reconcile_does_not_file_things_nobody_added():
    """The CLI is machine-wide; a realm is not. Discovery used to append every known plugin and
    server into whichever realm happened to be open when someone pressed a version scan — so
    installing something while working in one realm made it appear, unasked, in every other realm
    you later opened. A realm's catalogue is the record of what you allowed in there."""
    tk = {}
    changed = capscan.reconcile(tk, [{"name": "newplug", "version": "1.0.0", "latest": "", "marketplace": ""}],
                                [{"name": "newmcp", "remote": False}])
    assert changed is False
    assert not tk.get("plugins") and not tk.get("extensions") and not tk.get("connectors")


def test_reconcile_still_reports_versions_for_what_the_realm_has():
    """Discovery going quiet must not take version reconciliation with it — that is what the
    scan is for."""
    tk = {"plugins": [{"id": "mine", "name": "mine", "version": "1.0.0"}]}
    capscan.reconcile(tk, [{"name": "mine", "version": "1.0.0", "latest": "2.0.0", "marketplace": ""},
                           {"name": "notmine", "version": "1.0.0", "latest": "", "marketplace": ""}], [])
    assert tk["plugins"][0]["latest"] == "2.0.0"
    assert len(tk["plugins"]) == 1, "the one the realm never added stays out"


def test_discovery_is_available_when_explicitly_asked_for():
    """The 'pull the servers in' button is an invitation, made in the realm you are standing in."""
    tk = {}
    capscan.reconcile(tk, [{"name": "newplug", "version": "1.0.0", "latest": "", "marketplace": ""}],
                      [{"name": "newmcp", "remote": False}], discover=True)
    assert any(x["id"] == "newplug" and x.get("discovered") for x in tk["plugins"])
    # a local stdio server is an Extension, not a Connector
    assert any(c["id"] == "newmcp" and c.get("discovered") for c in tk["extensions"])
    assert not tk.get("connectors")


def test_reconcile_classifies_local_vs_remote_mcp():
    tk = {}
    capscan.reconcile(tk, [], [{"name": "localsrv", "remote": False},
                               {"name": "remotesrv", "remote": True}], discover=True)
    ext = next(c for c in tk["extensions"] if c["id"] == "localsrv")
    conn = next(c for c in tk["connectors"] if c["id"] == "remotesrv")
    assert ext["runs"] == "code" and ext["icon"] == "cap-extension"
    assert conn["runs"] == "service" and conn["icon"] == "cap-connector"


def test_reconcile_accepts_legacy_string_mcp():
    tk = {}
    capscan.reconcile(tk, [], ["oldstr"], discover=True)   # bare string -> local Extension
    assert any(c["id"] == "oldstr" for c in tk["extensions"])
