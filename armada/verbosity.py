"""How much an agent writes back.

ARMADA composes the whole system prompt (it passes `--system-prompt`, not `--append-system-prompt`),
so this is one more paragraph in something we already build — no extra CLI flag, no settings file.

The alternative was Claude Code's own `outputStyle`, which is the official mechanism and has a
built-in Concise style. Two things ruled it out: it's a settings-file field scoped to a session
rather than to one agent, and `--safe-mode` disables output styles — and ARMADA passes `--safe-mode`
on its no-tool and restricted paths. A verbosity setting that silently stops applying on some of
our own code paths is worse than not having one.

Two rules hold across every level, because "be brief" is otherwise an instruction to do less work
rather than to write less about it:

* Length is about the reply, never about the work. The same checking, reading and verifying happens
  at every level.
* Some things are never compressed: what went wrong and why, warnings, anything needing the owner's
  approval, and the exact content of an error. Those are the moments brevity costs the most.
"""
from __future__ import annotations
import json
from pathlib import Path
import logging
from .util import swallowed
log = logging.getLogger(__name__)

# id -> (label, one-line description for the UI, prompt block)
LEVELS: dict[str, tuple[str, str, str]] = {
    "terse": (
        "Terse",
        "The answer and nothing else.",
        "Answer in as few words as the question allows — often a sentence or a short list. No "
        "preamble, no restating the question, no summary of what you just did, no offers of "
        "further help. If the answer is a number, a name or a file path, give that.",
    ),
    "brief": (
        "Brief",
        "Result first, then only what's needed to act on it.",
        "Lead with the result. Then give only what the owner needs in order to act on it or judge "
        "it — usually a few lines. Cut preamble, narration of your own process, and closing "
        "summaries. Expand when they ask for detail.",
    ),
    "standard": (
        "Standard",
        "Result, the reasoning that matters, and what you ruled out.",
        "Lead with the result, then explain the reasoning that actually bears on it and anything "
        "significant you considered and rejected. Skip narration of routine steps. Aim for a few "
        "short paragraphs rather than a report.",
    ),
    "full": (
        "Detailed",
        "Full reasoning, alternatives and caveats.",
        "Give the result and then work through it: why this and not the alternatives, what the "
        "trade-offs are, which assumptions you made, and where you are uncertain. Prefer being "
        "complete over being short — but still lead with the answer, not with the journey to it.",
    ),
}

DEFAULT = "standard"          # what every realm and agent gets until someone changes it

# Never compressed, at any level. Brevity is cheapest to apply to the parts that matter least.
_ALWAYS = (
    "At every level: this governs how much you WRITE, never how much you CHECK — do the same "
    "thorough work regardless. And never abbreviate these, whatever the level says: what went "
    "wrong and why, warnings and risks, anything that needs the owner's approval, and the exact "
    "text of an error."
)


def normalise(value) -> str:
    """A stored level, or '' for anything unrecognised (which means 'inherit')."""
    v = str(value or "").strip().lower()
    return v if v in LEVELS else ""


def _json(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa — a missing or broken file just means "no override"
        swallowed(log, '_json: failed; returning a fallback')
        return {}


def realm_level(realm_root) -> str:
    return normalise(_json(Path(realm_root) / "realm.json").get("default_verbosity")) or DEFAULT


def agent_level(realm_root, agent_id: str) -> str:
    """Per-agent, falling back to the realm default — the same pattern as model and effort."""
    a = normalise(_json(Path(realm_root) / "agents" / str(agent_id) / "agent.json").get("verbosity"))
    return a or realm_level(realm_root)


def prompt_block(level: str) -> str:
    """The system-prompt section for a level. Always returns something: an agent that has never
    been configured should still be told what's expected, rather than being left to guess."""
    lvl = normalise(level) or DEFAULT
    label, _desc, body = LEVELS[lvl]
    return f"# How much to write ({label})\n{body}\n\n{_ALWAYS}"


def label(level: str) -> str:
    return LEVELS[normalise(level) or DEFAULT][0]
