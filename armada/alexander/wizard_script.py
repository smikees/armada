"""Everything Alexander says in the setup wizard, written in advance (ADR-012; docs/dev/ALEXANDER.md).

Scripted rather than generated: the first run costs nothing, can't fail on quota, sign-in or a
model's mood, and every line here is reviewed like any other copy. Voice as PROMPT.md: plain
English, British spelling, short sentences, no exclamation marks, no emoji; warm, direct, firm.

Placeholders in braces are filled by the wizard from the owner's own answers: {owner}, {realm},
{coordinator}, {collective}, {agent}, {count}, {folder}. A line only uses placeholders that exist
by its step. `line(step, key, **values)` fills one; a missing value leaves the brace text visible,
which the tests catch.
"""
from __future__ import annotations

import string

# The steps, in order. Each is (id, short title for the step rail).
STEPS: tuple[tuple[str, str], ...] = (
    ("welcome", "Welcome"),
    ("checks", "Check"),
    ("home", "Folder"),
    ("team", "Team"),
    ("capabilities", "Capabilities"),
    ("first-job", "First job"),
    ("tour", "Tour"),
    ("done", "Done"),
)

SCRIPT: dict[str, dict[str, str]] = {
    "welcome": {
        "intro": (
            "Good to meet you. I'm Alexander, ARMADA's guide. I'll get you set up, which takes a "
            "few minutes, and after that I'm the one to ask when something isn't clear or isn't "
            "working."),
        "what": (
            "ARMADA gives you a standing team of AI agents that work for you on this computer. "
            "They keep their own memory, work to your goals, and run jobs on a schedule, even "
            "when the window is closed. They run on your own Claude account, and everything "
            "they make stays in a folder you own."),
        "how": (
            "We'll check your computer is ready, choose where ARMADA keeps its work, appoint "
            "your first team, give them a few safe tools, and watch them do one real job. You "
            "can change every choice later."),
    },
    "checks": {
        "intro": "First, the things ARMADA needs. I'm checking them now.",
        "all_ok": "Everything's in place. On we go.",
        "no_claude": (
            "Claude Code isn't installed. ARMADA runs every agent through it, so nothing works "
            "without it. Install it with the button below, then check again. It takes a minute."),
        "signed_out": (
            "Claude Code is installed but not signed in. Sign in with your own Claude account. "
            "The sign-in happens in Claude's own window: ARMADA never sees your password."),
        "no_plan": (
            "You're signed in, but I can't confirm your Claude plan. Agents need a paid Claude "
            "plan or they'll stop at the first job. If you're sure yours is active, carry on."),
        "scheduler": (
            "The scheduler is ARMADA's background process: it runs your jobs on time, even with "
            "the window closed. It starts with Windows. I'll start it at the end."),
    },
    "home": {
        "intro": (
            "ARMADA keeps everything in one folder: every team, every agent's memory, every file "
            "they write. It's the one folder to back up. The suggestion below is fine for most "
            "people."),
        "realm": (
            "Now a name for your first realm. A realm is one team with its own agents, memory "
            "and jobs. Some people keep one for work and one for home. Call it whatever you'll "
            "recognise."),
        "folder_bad": (
            "That folder won't do: {reason}. Pick another, or use the suggestion."),
    },
    "team": {
        "intro": (
            "Time to appoint your team. Each template is a way of talking about the same thing: "
            "a coordinator who runs things, and members who each own an area. Pick the one that "
            "sounds like you; you can rename anyone later."),
        "state": (
            "A Cabinet, led by a Prime Minister. Ministers for finance, strategy, health, "
            "development, education, travel and the estate. The broadest team, for running a "
            "whole life."),
        "company": (
            "A Company, led by a CEO, with a CFO and a CMO. Small and businesslike, for work or "
            "a venture."),
        "crew": (
            "A Crew, led by a Captain, with a Navigator and a Quartermaster. The same idea with "
            "more salt in it."),
        "scratch": (
            "A blank realm. You name every agent yourself. Choose this if you already know "
            "exactly who you want."),
        "picked": (
            "{count} agents in your {collective}, with {coordinator} in charge. Untick anyone "
            "you don't need yet; you can appoint them later."),
        "blank_needs_one": "A team needs at least one agent. The first one you add leads it.",
    },
    "capabilities": {
        "intro": (
            "On their own, agents can think, write and remember. Capabilities let them do more: "
            "work with documents, use other services, reach further. Each one carries a risk "
            "level from what it can reach."),
        "curated": (
            "These are the ones we recommend to start with: the most useful for the least risk. "
            "All come from Anthropic, all are Low risk, and none needs an account. I've ticked "
            "the ones most people want."),
        "who": (
            "{coordinator} can use every one you switch on. The rest of the team gets a "
            "capability when you give it to them, on the Capabilities page."),
        "later": (
            "Connections to your own accounts, like email, calendars or Notion, aren't here on "
            "purpose. They act in your name, so you add them one at a time from Capabilities, "
            "after reading their review."),
        "none": "None is a perfectly good answer. You can add capabilities whenever you like.",
    },
    "first-job": {
        "intro": (
            "Let's see your team work. {coordinator} will write you a short first brief: who's "
            "on the team, what each of them can do for you, and three things worth asking for "
            "first."),
        "cost": (
            "This is a real run on your Claude plan. It takes a minute or two and uses about as "
            "much as a short conversation."),
        "running": "{coordinator} is working on it. You'll see the reply here as it's written.",
        "ok": (
            "That's your first brief. It's saved as a thread with {coordinator}, so you can "
            "reply to it and carry on the conversation."),
        "failed": (
            "That didn't work: {reason}. It isn't your fault and you haven't lost anything. "
            "Carry on, and ask me about it from the app when you're in; I'll see what went "
            "wrong."),
        "skipped": "No problem. You can run it any time from the Jobs page.",
    },
    "tour": {
        "intro": "Four places you'll use most. Everything else you'll find when you need it.",
        "overview": (
            "The Overview is the dashboard: your team, what's running, what's due, and your "
            "usage. You can rearrange it."),
        "agents": (
            "Each agent has a page: talk to them, set their model, give them memories, jobs "
            "and capabilities."),
        "jobs": (
            "Jobs is everything that runs on a schedule, and whether it worked. A job that "
            "fails tells you why."),
        "help": (
            "Help is the full manual. And I'm always one click away: the Alexander button at the "
            "top of every page, or Ask Alexander on anything that went wrong."),
    },
    "done": {
        "intro": "You're set up, {owner}. {realm} is ready.",
        "intro_noname": "You're set up. {realm} is ready.",
        "next": (
            "A good next step: tell {coordinator} what you're working towards. Goals are what "
            "the whole team plans around."),
        "sign_off": "I'll be here when you need me.",
    },
}


class _Keep(dict):
    """Leaves an unknown placeholder visible rather than raising, so a gap shows in review."""
    def __missing__(self, k):
        return "{" + k + "}"


def line(step: str, key: str, **values) -> str:
    return string.Formatter().vformat(SCRIPT[step][key], (), _Keep(values))


def placeholders(text: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(text) if f}
