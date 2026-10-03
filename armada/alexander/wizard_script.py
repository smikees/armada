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
    ("naming", "Naming"),
    ("team", "Team"),
    ("capabilities", "Capabilities"),
    ("first-job", "First task"),
    ("tour", "Tour"),
    ("done", "Done"),
)

SCRIPT: dict[str, dict[str, str]] = {
    "welcome": {
        "intro": (
            "Good to meet you, I'm Alexander. I will guide you through this setup. It takes "
            "~10 minutes. After that I'll continue to be your support contact for anything ARMADA-related."),
        "what": (
            "ARMADA gives you a standing team of AI agents that work for you on this computer. "
            "They keep their own memory, work towards your goals, and execute jobs on a schedule. "
            "They use your connected Anthropic, OpenAI or Google accounts, and everything "
            "they create stays in a folder you own, right here on this computer."),
        "how": (
            "Next, we'll check your environment is ready, choose ARMADA's folder, appoint "
            "your first agents, give them a set of starter tools, and watch them complete one real task. You "
            "can change every choice later."),
    },
    "checks": {
        "intro": "Choose one or more engines: Claude, Codex or Gemini. I'll check their CLIs and sign-ins separately.",
        "all_ok": "Everything's in place. On we go.",
        "no_claude": (
            "Claude Code isn't installed. Install it below if you want Claude models, or connect "
            "Codex or Gemini instead. One connected engine is enough."),
        "old_claude": (
            "Claude Code is installed, but it's older than ARMADA needs. Update it with the button "
            "below. It takes a minute, and your "
            "sign-in stays as it is."),
        "signed_out": (
            "An installed CLI still needs a provider sign-in. Use its Sign in button and complete "
            "the provider's instructions. ARMADA never sees your password."),
        "no_plan": (
            "You're signed in, but I can't confirm your plan. Availability and usage limits depend "
            "on your account. You can still continue and check it in App settings."),
        "scheduler": (
            "The scheduler is ARMADA's background process: it runs your jobs on time, even with "
            "the window hidden in the tray. Quitting ARMADA stops its scheduler. I'll start it at the end."),
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
    "naming": {
        "intro": "What should I call you, and what will you call this realm? Your agents will use your name in their profiles.",
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
            "A Company, led by a CEO, with a CFO, CMO and CPO. Small and businesslike, for work or "
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
            "These are the ones I recommend to start with: the most useful for the least risk. "
            "Each card shows its source, abilities and risk level. "
            "Document and writing skills start enabled; connections start disabled."),
        "who": (
            "The coordinator agent can use every one you switch on. The rest of the team gets a "
            "capability when you give it to them. Visit the Capabilities section after the setup "
            "to assign them to agents and complete the steps for the ones that require authentication."),
        "later": (
            "Everything you add here appears under Capabilities > User. Account connections and "
            "Windows MCP need the linked setup steps before an agent can use them."),
        "none": "None is a perfectly good answer. You can add capabilities whenever you like.",
    },
    "first-job": {
        "intro": (
            "Let's see your team work. {coordinator} will write you a short first brief: who's "
            "on the team, what each of them can do for you, and three things worth asking for "
            "first."),
        "cost": (
            "This is a real run on your connected provider plan. It takes a minute or two and uses about as "
            "much as a short conversation."),
        "running": "{coordinator} is working on it. The reply will appear here as it is formatted.",
        "ok": (
            "That's your first brief. It's saved as a thread with {coordinator}, so you can "
            "reply to it and carry on the conversation."),
        "failed": (
            "That didn't work: {reason}. It isn't your fault and you haven't lost anything. "
            "Carry on, and ask me about it from the app when you're in; I'll see what went "
            "wrong."),
        "skipped": "No problem. You can ask your coordinator for a first brief from their Threads page later.",
    },
    "tour": {
        "intro": "Four places you'll use most. Everything else you'll find when you need it.",
        "overview": (
            "The Overview is the dashboard: your team, what's running, what's due, and your "
            "usage and connected engine limits. You can rearrange widgets or promote them to sections."),
        "agents": (
            "Each agent has a page: talk to them, set their model, thinking and output verbosity, give them memories, jobs "
            "and capabilities."),
        "jobs": (
            "Jobs shows schedules, prompts, output and run history. Execution, audit findings and delivery "
            "are shown separately; completed does not mean an audit passed. Each job can inherit its "
            "agent's model settings or use its own, with up to three retries for retryable failures."),
        "help": (
            "Documentation is the searchable manual. I'm always one click away: the support button "
            "opens my companion window beside ARMADA, or use Ask Alexander on anything that went wrong."),
    },
    "done": {
        "intro": "You're set up, {owner}. {realm} is ready.",
        "intro_noname": "You're set up. {realm} is ready.",
        "next": (
            "A good next step: tell {coordinator} what you're working towards and set your first goals. Goals are what "
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
