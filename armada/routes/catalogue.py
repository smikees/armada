"""The Catalogue tab: search results, refresh, reveal, add, and the bring-a-link review
flow (ADR-004).

Split out of serve.py (Phase 2, 2.3) — a pure move, no behaviour change; the route table
stays in serve.py, only the handler bodies moved.
"""
from __future__ import annotations
import http.server, io, json, logging, os, subprocess, sys, threading, time, urllib.parse, contextlib
from pathlib import Path
from .. import activerealm, reader, render, scheduler, util, brand
from ..util import safe_seg
from . import _shared

log = logging.getLogger("armada.serve")


class CatalogueRoutes:
    def _get_catalogue(self):
        """Re-render the Catalogue's results area for one set of filters.

        Server-rendered rather than filtered in the browser because a search also queries the MCP
        registry over the network: one place that knows how to assemble the page beats a client
        merging two half-answers, one of which may have failed.
        """
        from .. import webui
        q = self._query()
        try:
            page = int(q.get("page", "0") or 0)
        except ValueError:
            page = 0
        self._send(200, webui.render_catalogue_results(
            reader.read(self.realm), self.realm, q=q.get("q", ""), source=q.get("source", ""),
            kind=q.get("kind", ""), author=q.get("author", ""), category=q.get("category", ""),
            page=page))

    def _catalogue_refresh(self, body: dict) -> dict:
        """Re-read the mirrored sources now, rather than waiting for the daily job."""
        from .. import catalogue
        r = catalogue.refresh()
        # The registry's size is counted by walking it, a few hundred paced requests — far too
        # slow to hold a click open, and too important to leave a day out of date when someone
        # has just asked for fresh data. So it runs behind the answer and lands on the next page
        # load. catalogue guards against two walks at once.
        # ...and, once the list is current, give this realm's discovered capabilities their real
        # names from it. Both jobs run behind the answer: adopt() may have to search the registry
        # per unmatched capability, which is seconds, and a click should not wait on it.
        realm_root = self.realm

        def _after():
            catalogue.adopt(realm_root)
            catalogue.refresh_registry_count()
        threading.Thread(target=_after, daemon=True).start()
        bad = [s for s, m in (r.get("sources") or {}).items() if not m.get("ok")]
        if bad and not r.get("total"):
            return {"ok": False, "error": "Couldn't reach: " + ", ".join(sorted(bad))}
        return {"ok": True, "total": r.get("total", 0), "stale": bad}

    def _catalogue_reveal(self, body: dict) -> dict:
        """Open the file manager at a skill the owner wrote, from its catalogue card.

        Resolved by catalogue key, never by a path from the request: the browser names the entry,
        the server looks up where that entry actually lives. Only the two local sources have a
        folder on this machine to show, so anything else is refused rather than guessed at.
        """
        from .. import catalogue
        e = catalogue.find(str(body.get("key") or ""))
        if not e or e.get("source") not in (catalogue.MINE, catalogue.INSTALLED):
            return {"ok": False, "error": "Only skills already on this computer have a file to open."}
        path = Path(str((e.get("install") or {}).get("path") or "")) / "SKILL.md"
        if not path.is_file():
            return {"ok": False, "error": "That skill's folder is no longer on this computer."}
        return self._reveal({"path": str(path.resolve())})

    def _catalogue_add(self, body: dict) -> dict:
        from .. import catalogue
        key = str(body.get("key") or "")
        if not key:
            return {"ok": False, "error": "no capability named"}
        return catalogue.add_to_realm(self.realm, key)

    # ---- bring a link (ADR-004) --------------------------------------------------------------
    # The review is a real agent turn — it can take a couple of minutes and, on the Claude engine,
    # spends the owner's subscription — so this blocks the request rather than polling a job. The
    # browser side (mcCatReview) already tells the owner to expect the wait.

    def _catalogue_review(self, body: dict) -> dict:
        from .. import catalogue
        from ..webui.catalogue import _cat_review_card, _cat_final_risk
        url = str(body.get("url") or "").strip()
        if not url:
            return {"ok": False, "error": "paste a link first"}
        result = catalogue.review_url(url)
        # Rendered here rather than in the browser so the report card can reuse the same
        # Runs/Can-touch icons and colours the User tab's cards use — one component, not a second
        # one hand-built in JS. The JSON fields stay too: mcCatAddLink round-trips them unchanged.
        if result.get("ok"):
            # Floored to the mechanical worst-case here, once, so the value that round-trips to
            # add_link_to_realm (and the tier it stores) already agrees with what the card just
            # showed — catalogue.py doesn't need to know about _cap_tier_why to get that right.
            result["risk"] = _cat_final_risk(result)
            # Checked across every realm ARMADA knows about, not just this one, so the card can say
            # which before Add is even offered — see catalogue.realms_with_capability.
            def _rp(p):
                try:
                    return str(Path(p).resolve())
                except OSError:
                    return str(p)
            where = catalogue.realms_with_capability(result.get("name") or "", url)
            here = _rp(self.realm)
            result["already_here"] = any(_rp(w["path"]) == here for w in where)
            result["already_elsewhere"] = [w["name"] for w in where if _rp(w["path"]) != here]
            result["html"] = _cat_review_card(result)
        return result

    def _catalogue_add_link(self, body: dict) -> dict:
        from .. import catalogue
        url = str(body.get("url") or "").strip()
        review = body.get("review")
        if not url or not isinstance(review, dict):
            return {"ok": False, "error": "review this link before adding it"}
        return catalogue.add_link_to_realm(self.realm, url, review)

    # ---- agent lifecycle -------------------------------------------------------------------
    # Retire and reinstate are one move in two directions; delete is the one that doesn't come
    # back. See armada/agentops.py for why retirement is a folder move rather than a flag.

