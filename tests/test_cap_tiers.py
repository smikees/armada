"""Risk tiers for capabilities.

A tier is a verdict shown as a colour, so every rule has to point at something checkable — what a
capability ships, what it runs, where it runs, who published it. Nothing here infers intent, and
nothing here is a model's opinion: a badge saying Caution must be answerable.

The rule these tests exist to protect: "Trusted" is a claim we only make about things we have
actually looked at.
"""
from armada.webui.capabilities import _cap_tier, _cap_tier_why


def tier(**it):
    return _cap_tier(it)


def why(**it):
    return _cap_tier_why(it)[1]


# --- hooks: the one ability that doesn't wait to be used -----------------------------------------

def test_hooks_are_caution_whoever_wrote_them():
    """A hook runs on the engine's lifecycle events whether or not an agent asked for anything, so
    no amount of good provenance downgrades it."""
    assert tier(touch=["hooks"]) == "red"
    assert tier(made="anthropic", touch=["hooks"]) == "red"
    assert tier(made="you", touch=["hooks"]) == "red"
    assert "hooks" in why(touch=["hooks"]).lower()


def test_hooks_outrank_a_reads_only_claim():
    """Shipping hooks contradicts 'reads only'; the thing it ships wins over what it says it does."""
    assert tier(runs="reads", touch=["hooks"]) == "red"


# --- the omission bug ----------------------------------------------------------------------------

def test_an_uninspected_third_party_thing_is_review_not_trusted():
    """This is the bug. A discovered plugin carried no runs and no touch, so it fell through to
    green — every plugin ARMADA found was rated Trusted purely because the fields were blank, and
    plugins are the kind that can carry hooks."""
    assert tier(name="mystery", source="3p") == "amber"
    assert "not inspected" in why(name="mystery", source="3p").lower()


def test_a_self_published_registry_entry_says_so():
    assert tier(name="x", source="3p", curated="registry") == "amber"
    assert "nobody has reviewed" in why(name="x", source="3p", curated="registry")


# --- provenance ----------------------------------------------------------------------------------

def test_your_own_capability_is_trusted():
    assert tier(source="custom") == "green"
    assert tier(made="you") == "green"


def test_anthropic_published_is_trusted():
    assert tier(made="anthropic") == "green"


def test_reads_only_is_trusted():
    assert tier(made="company", runs="reads") == "green"


# --- what it runs, and where ---------------------------------------------------------------------

def test_shell_access_is_caution():
    assert tier(made="anthropic", touch=["shell"]) == "red"
    assert "terminal" in why(touch=["shell"]).lower()


def test_third_party_code_on_your_computer_is_caution():
    assert tier(made="company", runs="code") == "red"


def test_an_outside_service_is_review_not_caution():
    """Your data leaves the machine, which is worth flagging — but a connector talking to a remote
    service is the normal case, not the alarming one. If every connector were Caution, Caution
    would stop discriminating. The tier matches the ability icons: amber abilities, amber stripe."""
    assert tier(made="company", runs="service") == "amber"


# --- the owner's override -------------------------------------------------------------------------

def test_an_explicit_tier_wins():
    """You looked and decided. That outranks anything derived."""
    assert tier(tier="green", made="company", runs="code") == "green"
    assert why(tier="green") == "Set by you."


def test_an_unknown_explicit_tier_is_ignored_rather_than_trusted():
    assert tier(tier="banana", source="3p") == "amber"


# --- every tier is explainable --------------------------------------------------------------------

def test_every_path_returns_a_reason():
    cases = [{}, {"touch": ["hooks"]}, {"touch": ["shell"]}, {"made": "you"},
             {"made": "anthropic"}, {"runs": "code"}, {"runs": "service"},
             {"runs": "reads"}, {"curated": "registry"}, {"tier": "red"}]
    for c in cases:
        t, reason = _cap_tier_why(c)
        assert t in ("green", "amber", "red")
        assert reason and reason[0].isupper() and reason.endswith("."), c


def test_the_shapes_capscan_writes_rate_by_what_they_do():
    """capscan files a remote MCP server as a service and a local one as code. The local one runs
    code on your machine with file access; the remote one exchanges data with a service you
    authenticated to. Those are different, and the tiers say so."""
    remote = {"source": "3p", "runs": "service", "touch": ["network"], "discovered": True}
    local = {"source": "3p", "runs": "code", "touch": ["files", "network"], "discovered": True}
    assert _cap_tier(remote) == "amber"
    assert _cap_tier(local) == "red"


def test_the_stripe_is_always_the_worst_icon_on_the_card():
    """A card whose abilities are all amber cannot wear a red stripe and leave you hunting for the
    reason. The tier is computed from the same list the icons are drawn from."""
    from armada.webui.capabilities import _ABILITY_CLR, _ABILITY_RANK, _COLOUR_TIER
    for ability in _ABILITY_RANK:
        it = {"touch": [ability]} if ability not in ("reads", "code", "service") else {"runs": ability}
        assert _cap_tier(it) == _COLOUR_TIER[_ABILITY_CLR[ability]], ability


def test_provenance_cannot_promote_something_past_what_it_can_reach():
    """A capability that writes to your disk is not made safe by who published it."""
    assert tier(made="anthropic", runs="code") == "red"
    assert tier(source="custom", touch=["shell"]) == "red"
