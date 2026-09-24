"""_catalogue_review (armada/routes/catalogue.py): the HTTP handler around catalogue.review_url().

The handler's own job, beyond calling review_url() and rendering the card, is the cross-realm
"already added" check (catalogue.realms_with_capability) — this is what lets the card say "Already
added to this realm" (and disable Add) or "Added to X, Y" (and leave Add active) before the owner
can create a duplicate. review_url() and realms_with_capability() are mocked here; they're tested
in their own right in test_catalogue_bring_link.py.
"""
import json

import pytest

from armada import catalogue as C
from armada.routes.catalogue import CatalogueRoutes


def _handler(realm_root):
    h = CatalogueRoutes.__new__(CatalogueRoutes)
    h.realm = str(realm_root)
    return h


@pytest.fixture
def realm(tmp_path):
    r = tmp_path / "realm"
    r.mkdir()
    (r / "realm.json").write_text(json.dumps({"name": "Test"}), encoding="utf-8")
    return r


def _fake_review(**over):
    r = {"ok": True, "name": "Weather MCP", "kind": "connectors", "publisher": "Acme",
         "runs": "service", "touch": ["network"], "risk": "medium",
         "recommendation": "r", "summary": "s", "warn": "", "confidence": "medium",
         "homepage": "https://github.com/acme/weather-mcp"}
    r.update(over)
    return r


def test_flags_a_capability_already_in_this_realm(realm, monkeypatch):
    monkeypatch.setattr(C, "review_url", lambda url, **kw: _fake_review())
    monkeypatch.setattr(C, "realms_with_capability",
                        lambda name, url: [{"name": "Test", "path": str(realm)}])
    h = _handler(realm)
    result = CatalogueRoutes._catalogue_review(h, {"url": "https://github.com/acme/weather-mcp"})
    assert result["already_here"] is True
    assert result["already_elsewhere"] == []
    assert "Already added to this realm" in result["html"]
    assert "Add to realm" not in result["html"], "the button reads Added, disabled, not Add to realm"


def test_flags_a_capability_added_in_another_realm(realm, tmp_path, monkeypatch):
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setattr(C, "review_url", lambda url, **kw: _fake_review())
    monkeypatch.setattr(C, "realms_with_capability",
                        lambda name, url: [{"name": "Cabinet2", "path": str(other)}])
    h = _handler(realm)
    result = CatalogueRoutes._catalogue_review(h, {"url": "https://github.com/acme/weather-mcp"})
    assert result["already_here"] is False
    assert result["already_elsewhere"] == ["Cabinet2"]
    assert "Added to Cabinet2" in result["html"]
    assert 'onclick="mcCatAddLink(this)"' in result["html"], "Add stays active for another realm"


def test_no_flag_when_nothing_matches_anywhere(realm, monkeypatch):
    monkeypatch.setattr(C, "review_url", lambda url, **kw: _fake_review())
    monkeypatch.setattr(C, "realms_with_capability", lambda name, url: [])
    h = _handler(realm)
    result = CatalogueRoutes._catalogue_review(h, {"url": "https://github.com/acme/weather-mcp"})
    assert result["already_here"] is False
    assert result["already_elsewhere"] == []
    assert "Already added" not in result["html"] and "Added to" not in result["html"]


def test_a_failed_review_is_returned_unenriched(realm, monkeypatch):
    """No point checking other realms for a review that didn't even succeed."""
    monkeypatch.setattr(C, "review_url", lambda url, **kw: {"ok": False, "error": "boom"})
    calls = []
    monkeypatch.setattr(C, "realms_with_capability", lambda name, url: calls.append(1) or [])
    h = _handler(realm)
    result = CatalogueRoutes._catalogue_review(h, {"url": "https://github.com/acme/weather-mcp"})
    assert result == {"ok": False, "error": "boom"}
    assert not calls, "realms_with_capability should not run for a failed review"
