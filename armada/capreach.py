"""Which engines a capability works with — its *reach* — and what a model change would cost.

ARMADA runs each agent on Claude, Codex or Gemini and keeps its context when the model changes.
Capabilities do not travel that freely, and pretending they do turns a predictable limit into a
job failure the owner discovers later. This module is the one place that answers three questions,
so the Capabilities page, the model pickers, the execution policy and the agent's own context can
never disagree:

* **Reach.** Does this capability work with *any engine*, or with *one* (a connector hosted in the
  Claude account, a ChatGPT app, a Claude Code plugin)?
* **One engine at a time.** Some services refuse concurrent AI platforms — authorising a second one
  disconnects the first (Interactive Brokers, per its own staff). Such a capability has a *current
  engine* and is unavailable on the others until the owner moves it.
* **Impact.** Which of an agent's capabilities stop working if it runs on another engine, and why.

Reach is derived from what the record already says (its endpoint, its engine bindings, its kind)
rather than stored, so it cannot drift from the record. Explicit fields win when present:
`reach` on rows ARMADA created for one engine, `exclusive` as an owner override, and
`exclusive_engine` once the owner has moved a one-engine-at-a-time capability.

Two capabilities are the same only if they reach the same server. A ChatGPT app and a Claude
connector that both say "Google Drive" are two rows, never one (see docs/dev/CAPABILITIES_UPGRADE.md).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlsplit

log = logging.getLogger(__name__)

ENGINES = ("claude", "codex", "gemini")
LABEL = {"claude": "Claude", "codex": "Codex", "gemini": "Gemini", "any": "Any engine"}
SCOPES = ("any",) + ENGINES

# Hosts that serve connectors living inside a provider account. Their endpoints are not portable:
# another engine cannot sign in to them.
_PROVIDER_HOSTS = {"claude": ("anthropic.com", "claude.ai", "claude.com")}

# Services that allow one AI platform per account at a time. Matched by endpoint host or by
# catalogue key. Generic: the owner can mark any other capability the same way.
_ONE_AT_A_TIME = (
    {"name": "Interactive Brokers", "hosts": ("api.ibkr.com", "ibkr.com"),
     "keys": ("com.ibkr/",),
     "why": "Interactive Brokers allows one AI platform per account at a time; authorising "
            "another one disconnects the previous one."},
)


@dataclass(frozen=True)
class Reach:
    """What one capability can be used with."""
    scope: str                 # "any" or one engine
    engines: tuple             # engines it can work with at all
    how: str                   # short label: "Open server", "Claude connector", …
    why: str                   # one sentence on the reach
    exclusive: bool = False    # one engine at a time
    engine: str = ""           # the current engine when exclusive
    exclusive_why: str = ""

    def available_on(self, engine: str) -> bool:
        if engine not in self.engines:
            return False
        return not self.exclusive or engine == self.engine

    @property
    def usable_engines(self) -> tuple:
        return tuple(e for e in self.engines if self.available_on(e))

    def blocked_reason(self, engine: str, name: str = "") -> str:
        """Why it does not work on `engine`, as a sentence; empty when it does."""
        it = name or "This capability"
        if self.available_on(engine):
            return ""
        if engine in self.engines and self.exclusive:
            return (f"{it} is connected to {LABEL.get(self.engine, self.engine)}, "
                    f"one engine at a time.")
        if self.scope in ENGINES:
            return f"{it} works only with {LABEL[self.scope]}: it is a {self.how}."
        return f"{it} is not available on {LABEL.get(engine, engine)}."

    def as_dict(self) -> dict:
        return {"scope": self.scope, "engines": list(self.engines), "how": self.how,
                "why": self.why, "exclusive": self.exclusive, "engine": self.engine,
                "exclusive_why": self.exclusive_why, "usable": list(self.usable_engines)}


def _https(value) -> str:
    v = str(value or "").strip()
    try:
        u = urlsplit(v)
    except ValueError:
        return ""
    return v if u.scheme == "https" and u.hostname else ""


def endpoint(cap: dict) -> str:
    """The capability's own remote MCP address, if it has one."""
    return _https((cap or {}).get("mcp_url")) or _https((cap or {}).get("command"))


def host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _host_in(h: str, suffixes) -> bool:
    return any(h == s or h.endswith("." + s) for s in suffixes)


def bindings(cap: dict) -> dict:
    rows = (cap or {}).get("provider_bindings")
    if not isinstance(rows, dict):
        return {}
    return {p: r for p, r in rows.items()
            if p in ENGINES and isinstance(r, dict) and r and r != {"disabled": True}}


def is_claude_import(cap: dict) -> bool:
    """A connector Claude set up arrives as `claude.ai <name>` / `claude_ai_<name>`."""
    cid = str((cap or {}).get("id") or "")
    return cid.lower().startswith(("claude.ai ", "claude_ai_"))


def _provider_hosted(url: str) -> str:
    h = host(url)
    for engine, suffixes in _PROVIDER_HOSTS.items():
        if h and _host_in(h, suffixes):
            return engine
    return ""


def known_one_at_a_time(cap: dict) -> dict | None:
    """The known service entry this capability belongs to, if it allows one platform at a time."""
    urls = [endpoint(cap)] + [_https(r.get("endpoint")) for r in bindings(cap).values()]
    hosts = {host(u) for u in urls if u}
    key = str((cap or {}).get("catalogue_key") or "").lower()
    for svc in _ONE_AT_A_TIME:
        if any(_host_in(h, svc["hosts"]) for h in hosts if h):
            return svc
        if key and any(k in key for k in svc["keys"]):
            return svc
    return None


def _connector_reach(cap: dict) -> tuple:
    """(scope, how, why) for a connector row."""
    b = bindings(cap)
    app = any("app_id" in r for r in b.values())
    servers = {p: r for p, r in b.items() if "server_name" in r}
    ep = endpoint(cap)
    if not ep:
        # Bound registrations may carry the public endpoint even when the row has none.
        ep = next((_https(r.get("endpoint")) for r in servers.values() if _https(r.get("endpoint"))), "")
    if app and not ep and not servers and not is_claude_import(cap):
        return ("codex", "ChatGPT app",
                "A native app in your ChatGPT account; only Codex models can use it.")
    if ep:
        hosted = _provider_hosted(ep)
        if hosted:
            return (hosted, f"{LABEL[hosted]} connector",
                    f"Hosted by the provider inside your {LABEL[hosted]} account; "
                    f"other engines can't reach it.")
        if (is_claude_import(cap) and not known_one_at_a_time(cap)
                and not any(p != "claude" for p in servers)):
            # Claude set this up through your Claude account. Its address may be public, but
            # getting another engine to sign in to it is service-specific (Google's servers need
            # your own OAuth client, for one), so it is not promised to other engines. Add the
            # service for them separately when it offers a route.
            return ("claude", "Claude connector",
                    "Set up through your Claude account. Other engines need their own version of "
                    "this service; add it for them from Add a capability.")
        return ("any", "Open server",
                "A public MCP server: every engine can use it, and each one signs in separately.")
    if is_claude_import(cap) or (len(servers) == 1 and "claude" in servers):
        return ("claude", "Claude connector",
                "Set up in your Claude account; other engines can't reach it.")
    if len(servers) == 1:
        engine = next(iter(servers))
        return (engine, f"{LABEL[engine]} connection",
                f"Registered only in {LABEL[engine]}; add its server to other engines to use it there.")
    return ("any", "Not linked yet",
            "Not linked to any engine yet. Link an engine connection to use it.")


def reach(kind: str, cap: dict) -> Reach:
    """The reach of one realm capability. Never raises; unknown shapes read as any engine."""
    cap = cap or {}
    explicit = str(cap.get("reach") or "").lower()
    if kind == "skills":
        scope, how, why = ("any", "Skill", "A skill folder: every engine can follow it.")
    elif kind == "extensions":
        scope, how, why = ("any", "Local extension",
                           "Runs on this computer; register the same command in each engine you use.")
    elif kind == "plugins":
        scope, how, why = ("claude", "Claude Code plugin",
                           "A Claude Code plugin; plugin formats are engine-specific.")
    else:
        scope, how, why = _connector_reach(cap)
    if explicit in SCOPES and explicit != scope:
        scope = explicit
        if explicit in ENGINES:
            how = "ChatGPT app" if (explicit == "codex" and any(
                "app_id" in r for r in bindings(cap).values())) else f"{LABEL[explicit]} connection"
            why = f"Set up for {LABEL[explicit]} only; other engines can't use it."
        else:
            how, why = "Any engine", "Works with every engine; each one signs in separately."
    engines = ENGINES if scope == "any" else (scope,)

    svc = known_one_at_a_time(cap) if kind == "connectors" else None
    flag = cap.get("exclusive")
    exclusive = bool(flag) if isinstance(flag, bool) else bool(svc)
    current, ex_why = "", ""
    if exclusive and len(engines) > 1:
        ex_why = (svc or {}).get("why") or ("Marked as one engine at a time: connecting it to "
                                            "another engine disconnects the current one.")
        want = str(cap.get("exclusive_engine") or "").lower()
        if want in engines:
            current = want
        else:
            b = bindings(cap)
            if is_claude_import(cap) or "claude" in b:
                current = "claude"
            else:
                current = next((e for e in ENGINES if e in b), engines[0])
    else:
        exclusive = False
    return Reach(scope, tuple(engines), how, why, exclusive, current, ex_why)


def entry_reach(entry: dict) -> str:
    """Reach of a catalogue entry before it is added: 'any' or one engine."""
    from . import catalogue as cat
    src = str((entry or {}).get("source") or "")
    kind = str((entry or {}).get("kind") or "")
    if cat.is_marketplace(src) or kind == "plugins":
        return "claude"
    if kind == "connectors":
        for r in ((entry or {}).get("install") or {}).get("remotes") or []:
            hosted = _provider_hosted(str((r or {}).get("url") or ""))
            if hosted:
                return hosted
    return "any"


# --------------------------------------------------------------------------- agents

def agent_engine(realm_root, agent, job=None, model: str | None = None) -> str:
    """The engine an agent (or one of its jobs) runs on, optionally with a model swapped in."""
    from .engine.selection import engine_for, read_config
    from pathlib import Path
    a = agent
    if isinstance(agent, str):
        a = read_config(Path(realm_root) / "agents" / agent / "agent.json")
    a = dict(a or {})
    j = dict(job or {}) if job else None
    if model is not None:
        if j is not None:
            j["model"] = model
        else:
            a["model"] = model
    return engine_for(realm_root, a, j)


def impact(realm_root, agent, engine: str) -> list:
    """Every capability the agent may use that would NOT work on `engine`, with the reason.

    Ordered by kind, then name. An agent with nothing granted loses nothing.
    """
    from . import capabilities as caps
    out = []
    try:
        usable = caps.usable(realm_root, agent)
    except Exception:  # noqa — an unreadable agent has nothing to lose that we can name
        from .util import swallowed
        swallowed(log, 'impact: agent grants unreadable; reporting nothing lost')
        return out
    for kind in caps.KINDS:
        for cap in sorted(usable.get(kind) or [], key=lambda c: str(c.get("name") or c.get("id") or "").lower()):
            r = reach(kind, cap)
            if not r.available_on(engine):
                name = str(cap.get("name") or cap.get("id") or "")
                out.append({"id": str(cap.get("id") or name), "name": name, "kind": kind,
                            "why": r.blocked_reason(engine, name), "scope": r.scope,
                            "exclusive": r.exclusive, "current": r.engine})
    return out


def impact_text(display: str, engine: str, lost: list, limit: int = 6) -> str:
    """One line for a model picker or a confirmation."""
    who = display or "This agent"
    eng = LABEL.get(engine, engine)
    if not lost:
        return f"All of {who}'s capabilities work with {eng}."
    names = [x["name"] for x in lost[:limit]]
    more = len(lost) - len(names)
    listed = ", ".join(names) + (f" and {more} more" if more > 0 else "")
    return f"On {eng}, {who} can't use {listed}."


def sections(realm_root) -> dict:
    """{scope: {kind: [cap, ...]}} for the whole realm catalogue, in display order."""
    from . import capabilities as caps
    out = {s: {k: [] for k in caps.KINDS} for s in SCOPES}
    for kind, cap in caps.catalogue_flat(realm_root):
        out[reach(kind, cap).scope][kind].append(cap)
    return out


def engine_scope(kind: str, cap: dict) -> tuple:
    """Engines on which an MCP capability may be admitted to a turn right now."""
    return reach(kind, cap).usable_engines
