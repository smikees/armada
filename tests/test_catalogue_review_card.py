"""_cat_review_card: the bring-a-link report, rendered server-side.

Moved out of client JS (Mihai's feedback, 2026-09-21: the old card was one small, unstructured
paragraph) so it can reuse the same Runs/Can-touch iconography and risk colours the User tab's
declared-vs-observed panel uses (_cap_iconcluster), and lead with a short assessment rather than
burying it inside the full Step 5 evidence report.
"""
from armada.webui.catalogue import _cat_review_card, _paragraph_break_before_labels, _cat_final_risk


def _review(**over):
    r = {"ok": True, "name": "Weather MCP", "kind": "connectors", "publisher": "Acme",
         "runs": "service", "touch": ["network"], "risk": "medium",
         "recommendation": "Talks to a weather API over https. No surprises.",
         "summary": "BUCKET — Connector.\n\nRUNS — service, talks to api.weather.example.",
         "warn": "", "confidence": "medium", "homepage": "https://github.com/acme/weather-mcp"}
    r.update(over)
    return r


def test_the_assessment_leads():
    html = _cat_review_card(_review())
    assert "Armada’s assessment:" in html
    assert "Talks to a weather API over https" in html
    assert html.index("Armada’s assessment:") < html.index("BUCKET")


def test_name_and_publisher_are_shown():
    html = _cat_review_card(_review())
    assert "Weather MCP" in html
    assert "by Acme" in html


def test_no_publisher_line_when_none_was_found():
    html = _cat_review_card(_review(publisher=""))
    assert "by " not in html


def test_the_confidence_pill_is_gone():
    """Mihai, 2026-09-21: showing both 'medium risk' and 'medium confidence' pills reads as two
    conflicting verdicts. Only the risk pill remains — confidence isn't shown at all any more,
    whatever value the review gave."""
    html = _cat_review_card(_review(confidence="high"))
    assert "confidence" not in html.lower()


def test_a_warning_is_flagged_and_an_absent_one_is_not():
    flagged = _cat_review_card(_review(warn="fetches a CDN font on every load, unannounced"))
    assert "Flagged" in flagged and "CDN font" in flagged
    clean = _cat_review_card(_review(warn=""))
    assert "Flagged" not in clean


def test_runs_and_touch_reuse_the_user_tabs_icon_cluster():
    """Same component as the User tab's cards use (_cap_iconcluster) — the captions are how you'd
    spot it. Now inline on the title row, next to 'by X', not a separate band."""
    html = _cat_review_card(_review(runs="code", touch=["files", "network"]))
    assert "Runs" in html and "Can touch" in html


def test_nothing_touches_when_the_review_found_no_abilities():
    html = _cat_review_card(_review(runs="", touch=[]))
    assert "Can touch" not in html


def test_the_full_report_is_collapsed_behind_full_review():
    html = _cat_review_card(_review())
    assert "Full review" in html
    assert "<details" in html
    # the long evidence text is there, just inside the collapsed section, not inline
    assert "api.weather.example" in html


def test_the_full_review_toggle_uses_the_animated_caret():
    """Same caret mechanics as a capability card's own expand arrow (.mc-cap-caret, brand.css),
    not the plain static chevron it used to be."""
    html = _cat_review_card(_review())
    assert 'class="mc-cat-full"' in html
    assert 'class="mc-cap-caret"' in html


def test_no_full_review_section_when_theres_nothing_beyond_the_assessment():
    same = "Talks to a weather API over https. No surprises."
    html = _cat_review_card(_review(recommendation=same, summary=same))
    assert "Full review" not in html


def test_falls_back_to_the_summary_when_no_recommendation_was_given():
    html = _cat_review_card(_review(recommendation="", summary="only the long report here"))
    assert "only the long report here" in html
    assert html.index("Armada’s assessment:") < html.index("only the long report here")


def test_the_add_button_round_trips_through_mccataddlink():
    html = _cat_review_card(_review())
    assert 'onclick="mcCatAddLink(this)"' in html
    assert "Add to realm" in html


def test_untrusted_text_is_escaped():
    html = _cat_review_card(_review(name="<script>alert(1)</script>"))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# --- the risk bucket (Mihai, 2026-09-21: start the assessment with one of three buckets, and
# never show it softer than what Runs/Can-touch alone would earn elsewhere in the app) ---------

def test_the_risk_pill_leads_and_uses_the_agents_own_bucket():
    html = _cat_review_card(_review(risk="high"))
    assert "HIGH RISK" in html
    assert "var(--status-bad)" in html
    assert html.index("HIGH RISK") < html.index("Armada’s assessment:")


def test_a_reads_only_review_with_nothing_to_touch_falls_back_to_low():
    """No risk field given: the same mechanical read every other unrated capability gets
    (_cap_tier_why), from runs/touch alone."""
    html = _cat_review_card(_review(risk="", runs="reads", touch=[]))
    assert "LOW RISK" in html
    assert "var(--status-ok)" in html


def test_shell_reach_falls_back_to_high_with_no_risk_given():
    html = _cat_review_card(_review(risk="", runs="code", touch=["shell"]))
    assert "HIGH RISK" in html


def test_an_invalid_risk_value_also_falls_back():
    html = _cat_review_card(_review(risk="extremely dangerous", runs="reads", touch=[]))
    assert "LOW RISK" in html


def test_a_soft_agent_verdict_is_floored_to_the_mechanical_worst_case():
    """The reported bug: the agent can call shell reach 'medium', but a capability that runs
    shell commands is red everywhere else in the app (_cap_tier_why) — the card can't be softer
    than that just because the review's own word was gentler."""
    html = _cat_review_card(_review(risk="medium", runs="code", touch=["shell"]))
    assert "HIGH RISK" in html
    assert "MEDIUM RISK" not in html


def test_the_agents_own_higher_verdict_is_not_lowered():
    """The floor only ever raises the bucket — an agent judging something worse than the
    mechanical read (nothing declared risky, but a real concern found in Step 5) keeps its word."""
    html = _cat_review_card(_review(risk="high", runs="reads", touch=[]))
    assert "HIGH RISK" in html


def test_cat_final_risk_matches_the_card():
    review = _review(risk="medium", runs="code", touch=["shell"])
    assert _cat_final_risk(review) == "high"


# --- full-review readability ------------------------------------------------------------------

def test_paragraph_break_before_labels_splits_a_dense_report():
    text = "BUCKET — Connector, and the record should say connector. RUNS — service. CAN TOUCH — network only."
    out = _paragraph_break_before_labels(text)
    parts = [p for p in out.split("\n\n") if p]
    assert len(parts) == 3
    assert parts[0].startswith("BUCKET")
    assert parts[1].startswith("RUNS")
    assert parts[2].startswith("CAN TOUCH")


def test_paragraph_break_leaves_ordinary_prose_alone():
    text = "This is a normal sentence about a URL, not a command, with no labels in it."
    assert _paragraph_break_before_labels(text) == text


def test_paragraph_break_does_not_split_a_compound_label():
    """The reported bug: 'DECLARED vs OBSERVED —' is one phrase the agent wrote as its own label,
    but the all-caps scan used to find 'OBSERVED —' on its own and break the line right after
    'vs', reading as broken markup rather than a label."""
    text = "No surprises here. DECLARED vs OBSERVED — no under-declaration found, matches the record."
    out = _paragraph_break_before_labels(text)
    assert "DECLARED vs\n\nOBSERVED" not in out
    assert "\n\n" not in out, "neither half of the compound label is a real section label here"


def test_the_full_review_section_renders_separate_paragraphs():
    dense = "BUCKET — Connector. RUNS — service. EVIDENCE — see server.js line 12."
    html = _cat_review_card(_review(summary=dense))
    assert html.count("<p>") >= 3


# --- already added, in this realm or another (the reported bug: a link for a capability already
# in the realm reviewed clean and added a second time) -------------------------------------------

def test_already_here_disables_add_and_flags_the_realm():
    html = _cat_review_card(_review(already_here=True, already_elsewhere=[]))
    assert "disabled" in html
    assert "Already added to this realm" in html
    assert 'onclick="mcCatAddLink(this)"' not in html


def test_already_in_another_realm_keeps_add_active():
    html = _cat_review_card(_review(already_here=False, already_elsewhere=["Cabinet2"]))
    assert "Added to Cabinet2" in html
    assert "disabled" not in html
    assert 'onclick="mcCatAddLink(this)"' in html
    assert "Add to realm" in html


def test_already_in_several_other_realms_lists_them():
    html = _cat_review_card(_review(already_here=False, already_elsewhere=["Cabinet2", "Skunkworks"]))
    assert "Added to Cabinet2, Skunkworks" in html


def test_neither_here_nor_elsewhere_shows_no_status_line():
    html = _cat_review_card(_review())     # no already_here/already_elsewhere keys at all
    assert "Already added" not in html
    assert "Added to" not in html
    assert 'onclick="mcCatAddLink(this)"' in html


def test_already_here_wins_over_already_elsewhere():
    """A capability can be in several realms at once; the button only cares about this one."""
    html = _cat_review_card(_review(already_here=True, already_elsewhere=["Cabinet2"]))
    assert "Already added to this realm" in html
    assert "Added to Cabinet2" not in html
