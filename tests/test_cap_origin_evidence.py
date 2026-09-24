"""What a discovered capability IS, established from evidence rather than from its name.

The bug that prompted this: a realm holding a local MCP server called `filesystem` put
"already in Cabinet2" on all eleven registry results for that word — `chroot-filesystem-jail-mcp`
among them — and disabled Add on every one. A tick that appears against things you do not have is
worse than no tick at all: this page exists to tell you what you are running.

The cause was two decisions compounding. Discovery kept only the server's NAME, throwing away the
command line that says what it actually is; and the "already installed" hint matched names by
containment, which for a word as generic as `filesystem` matches nearly everything.
"""
import json

import pytest

from armada import capscan
from armada import catalogue as C


# --- the command line is the evidence ---------------------------------------------------------

def test_the_command_is_kept_not_just_the_name(monkeypatch):
    """It was read for the "://" test and then discarded. A bare name cannot identify anything."""
    line = (r"filesystem: node C:\Users\M\AppData\Roaming\Claude\Claude Extensions"
            r"\ant.dir.ant.anthropic.filesystem\dist\index.js - OK")
    monkeypatch.setattr(capscan, "_run", lambda args: (0, "Checking MCP server health\n\n" + line))
    got = capscan.list_mcp()
    assert len(got) == 1
    assert "Claude Extensions" in got[0]["command"]
    assert got[0]["remote"] is False


@pytest.mark.parametrize("cmd,bundle,pub", [
    (r"node C:\Users\M\AppData\Roaming\Claude\Claude Extensions\ant.dir.ant.anthropic.filesystem\dist\index.js",
     "ant.dir.ant.anthropic.filesystem", "anthropic"),
    (r"node C:\x\Claude Extensions\ant.dir.gh.anthropic.pdf-server-mcp\dist\index.js --stdio",
     "ant.dir.gh.anthropic.pdf-server-mcp", "anthropic"),
])
def test_a_claude_desktop_extension_names_itself(cmd, bundle, pub):
    """Its bundle id carries its own provenance, which is a better answer than any name search."""
    got = capscan.extension_identity(cmd)
    assert got["id"] == bundle and got["publisher"] == pub


def test_a_bundle_id_of_another_shape_claims_no_publisher():
    """Better no publisher than one guessed out of a dotted string."""
    got = capscan.extension_identity(r"node /x/Claude Extensions/com.example.thing/index.js")
    assert got["id"] == "com.example.thing" and got["publisher"] == ""


def test_an_ordinary_command_is_not_an_extension():
    assert capscan.extension_identity("uvx windows-mcp") == {}
    assert capscan.extension_identity("") == {}


def test_identifying_it_closes_the_question():
    prov = capscan._discovered_provenance(
        r"node C:\x\Claude Extensions\ant.dir.ant.anthropic.filesystem\dist\index.js")
    assert prov["identified"] is True
    assert prov["origin"] == "Claude Desktop extension"
    assert prov["made_by"] == "Anthropic"


def test_a_plain_command_records_evidence_without_claiming_an_answer(monkeypatch):
    prov = capscan._discovered_provenance("uvx windows-mcp")
    assert prov["command"] == "uvx windows-mcp"
    assert "identified" not in prov and "origin" not in prov


# --- claude.ai connectors have spaces in their names -------------------------------------------

def test_a_server_name_with_spaces_is_not_dropped(monkeypatch):
    """Claude's own connectors are all called things like "claude.ai Google Drive". Rejecting
    spaces dropped every one of them, and with them the URL that says what each is."""
    out = ("claude.ai Google Drive: https://drivemcp.googleapis.com/mcp/v1 - OK\n"
           "Checking MCP server health\n")
    monkeypatch.setattr(capscan, "_run", lambda args: (0, out))
    got = capscan.list_mcp()
    assert [s["name"] for s in got] == ["claude.ai Google Drive"]
    assert got[0]["remote"] is True
    assert got[0]["command"] == "https://drivemcp.googleapis.com/mcp/v1"


def test_prose_without_a_status_separator_is_not_a_server(monkeypatch):
    monkeypatch.setattr(capscan, "_run", lambda args: (0, "Note: something the CLI wanted to say\n"))
    assert capscan.list_mcp() == []


# --- what it runs beats what it is called ------------------------------------------------------

def test_a_declared_package_settles_a_name_collision():
    """`windows-mcp` resembles two published servers. One declares the pypi package the machine
    actually runs; the other declares something else entirely."""
    right = C._entry(C.REGISTRY, "extensions", "io.github.CursorTouch/Windows-MCP", "", "",
                     install={"packages": [{"identifier": "windows-mcp", "runtimeHint": "uvx"}]})
    wrong = C._entry(C.REGISTRY, "extensions", "io.github.Other/windows-mcp-server", "", "",
                     install={"packages": [{"identifier": "windows-management-mcp-server"}]})
    cap = {"id": "windows-mcp", "command": "uvx windows-mcp"}
    assert C._command_matches(cap, right) is True
    assert C._command_matches(cap, wrong) is False


def test_a_package_name_must_match_whole():
    cap = {"id": "x", "command": "uvx windows-mcp"}
    e = C._entry(C.REGISTRY, "extensions", "a/b", "", "",
                 install={"packages": [{"identifier": "windows"}]})
    assert C._command_matches(cap, e) is False


def test_the_same_service_on_a_different_endpoint_still_matches():
    """The realm's IBKR connector points at .../v1/api/mcp; the registry declares .../mcp-public.
    The authenticated endpoint and the open one, the same service either way."""
    e = C._entry(C.REGISTRY, "connectors", "com.ibkr/interactive-brokers-ibkr", "", "",
                 install={"remotes": [{"url": "https://api.ibkr.com/v1/api/mcp-public"}]})
    cap = {"id": "claude_ai_Interactive_Brokers_IBKR",
           "command": "https://api.ibkr.com/v1/api/mcp"}
    assert C._command_matches(cap, e) is True


def test_a_different_vendor_does_not_match():
    e = C._entry(C.REGISTRY, "connectors", "a/b", "", "",
                 install={"remotes": [{"url": "https://api.example.com/mcp"}]})
    assert C._command_matches({"id": "x", "command": "https://api.ibkr.com/mcp"}, e) is False


def test_no_command_is_no_evidence():
    e = C._entry(C.REGISTRY, "connectors", "a/b", "", "",
                 install={"remotes": [{"url": "https://api.ibkr.com/mcp"}]})
    assert C._command_matches({"id": "x"}, e) is False


# --- the reported bug --------------------------------------------------------------------------

@pytest.fixture
def realm(tmp_path):
    r = tmp_path / "realm"
    r.mkdir()
    return r


def _write(realm, toolkit):
    (realm / "realm.json").write_text(json.dumps({"name": "Cabinet2", "toolkit": toolkit}),
                                      encoding="utf-8")


def _registry_lookalikes():
    return [C._entry(C.REGISTRY, "extensions", i, n, "")
            for i, n in (("io.github.bytedance/mcp-server-filesystem", "mcp-server-filesystem"),
                         ("com.pulsemcp/remote-filesystem", "com.pulsemcp/remote-filesystem"),
                         ("io.github.x/chroot-filesystem-jail-mcp", "Execute chroot-filesystem-jail-mcp"),
                         ("io.github.y/filesystem", "Filesystem"))]


def test_a_generic_name_no_longer_ticks_every_lookalike(realm, monkeypatch):
    """Eleven results, eleven ticks, Add disabled on all of them — for one local server sharing a
    common word with them."""
    _write(realm, {"extensions": [{"id": "filesystem", "name": "filesystem", "source": "3p",
                                   "discovered": True, "identified": True,
                                   "origin": "Claude Desktop extension"}]})
    monkeypatch.setattr(C, "_known_realms", lambda: [str(realm)])
    inst = C.installed_keys([str(realm)], _registry_lookalikes())
    assert inst == {}, f"still ticking: {sorted(inst)}"


def test_an_unidentified_generic_name_still_only_matches_exactly(realm, monkeypatch):
    """Before it is identified, the hint falls back to names — but exactly, not by containment.
    `chroot-filesystem-jail-mcp` contains the word and is not the thing."""
    _write(realm, {"extensions": [{"id": "filesystem", "name": "filesystem", "source": "3p",
                                   "discovered": True}]})
    monkeypatch.setattr(C, "_known_realms", lambda: [str(realm)])
    inst = C.installed_keys([str(realm)], _registry_lookalikes())
    assert set(inst) == {"mcp-registry/extensions/io.github.y/filesystem"}


def test_a_capability_added_from_the_catalogue_matches_only_its_own_key(realm, monkeypatch):
    _write(realm, {"skills": [{"id": "frontend-design", "name": "Frontend design", "source": "3p",
                               "catalogue_key": "anthropic-skills/skills/frontend-design"}]})
    monkeypatch.setattr(C, "_known_realms", lambda: [str(realm)])
    known = [C._entry(C.SKILLS, "skills", "frontend-design", "Frontend design", ""),
             C._entry(C.REGISTRY, "extensions", "io.github.z/frontend-design", "Frontend design", "")]
    inst = C.installed_keys([str(realm)], known)
    assert set(inst) == {"anthropic-skills/skills/frontend-design"}


def test_adopt_leaves_an_identified_capability_alone(realm):
    """We know it is Anthropic's Claude Desktop extension. A registry server with a similar name
    is not new information."""
    _write(realm, {"extensions": [{"id": "filesystem", "name": "filesystem", "source": "3p",
                                   "identified": True, "origin": "Claude Desktop extension",
                                   "made_by": "Anthropic"}]})
    r = C.adopt(realm, entries=_registry_lookalikes(), search=False)
    assert r["changed"] == []
    got = json.loads((realm / "realm.json").read_text(encoding="utf-8-sig"))
    assert got["toolkit"]["extensions"][0]["made_by"] == "Anthropic"


# --- backfilling what is already in a realm ------------------------------------------------------

def test_a_rescan_identifies_servers_the_realm_already_has():
    """Everything on disk was discovered as a bare name before the command was kept, so the items
    that most need identifying are exactly the ones an add-only pass would never touch."""
    tk = {"extensions": [{"id": "filesystem", "name": "filesystem", "source": "3p",
                          "discovered": True}]}
    mcp = [{"name": "filesystem", "remote": False,
            "command": r"node C:\x\Claude Extensions\ant.dir.ant.anthropic.filesystem\dist\index.js"}]
    assert capscan.reconcile(tk, [], mcp) is True
    it = tk["extensions"][0]
    assert it["identified"] is True and it["made_by"] == "Anthropic"
    assert it["origin"] == "Claude Desktop extension"


def test_a_rescan_does_not_overwrite_a_source_you_chose():
    """You added it from the Catalogue. What the CLI happens to call it does not outrank that."""
    tk = {"extensions": [{"id": "windows-mcp", "name": "windows-mcp",
                          "catalogue_key": "mcp-registry/extensions/io.github.cursortouch/windows-mcp",
                          "origin": "MCP registry", "made_by": "CursorTouch"}]}
    mcp = [{"name": "windows-mcp", "remote": False,
            "command": r"node C:\x\Claude Extensions\ant.dir.ant.anthropic.filesystem\i.js"}]
    capscan.reconcile(tk, [], mcp)
    it = tk["extensions"][0]
    assert it["origin"] == "MCP registry" and it["made_by"] == "CursorTouch"
    assert it["command"], "the evidence is still recorded, it just doesn't win"
