"""ARMADA domain model (neutral ontology).

The realm is the files; these dataclasses are the in-memory view a reader
produces and a renderer consumes. Nothing here is engine- or theme-specific.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

# --- context window / compaction sizing -------------------------------------------------------
# ARMADA calls `claude -p` fresh each turn, so the real limit is the model's CONTEXT WINDOW (input
# tokens). Claude Code auto-compacts near ~95% of it. Opus 4.x/5 and Haiku ship a 200K window;
# Sonnet 5 and Fable ship a native 1M window. ARMADA summarises a thread's history well before the
# assembled prompt approaches the window, leaving comfortable room for the reply.
_CHARS_PER_TOKEN = 4                 # matches the app's token estimate (chars // 4)
_COMPACT_FRACTION = 0.75             # summarise history before it reaches this share of the window


def context_window_tokens(model_label: str) -> int:
    d = (model_label or "").lower()
    if "fable" in d or "sonnet 5" in d or "sonnet-5" in d:
        return 1_000_000
    return 200_000


def compaction_threshold_chars(model_label: str) -> int:
    """Char budget for a thread's history before ARMADA compacts it — derived from the model's real
    context window, not an arbitrary constant."""
    return int(context_window_tokens(model_label) * _COMPACT_FRACTION * _CHARS_PER_TOKEN)


@dataclass
class Skill:
    """A capability enabled for an agent — pinned by source+version, gated by permission scopes.
    SPEC §6: scopes are drawn from files | network | connectors | shell."""
    id: str
    source: str = "builtin"            # builtin | npx:<pkg> | uvx:<pkg> | path:<...>
    version: str = "*"                 # pinned version ("*" = unpinned, flagged by doctor)
    scopes: list[str] = field(default_factory=list)   # files | network | connectors | shell

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"


@dataclass
class Job:
    id: str
    name: str
    cadence: str                       # human-readable schedule, e.g. "mon-fri 14:00"
    summary: str = ""                  # one line: what this job does, shown beside the name
    enabled: bool = True               # off = never fires on its own; "Run now" still works
    kind: str = "agent"                # agent (LLM via engine) | command (deterministic script)
    report_task: Optional[str] = None  # id the run-reports actually carry (alias)
    last_status: Optional[str] = None  # ok | warn | error | quiet | None
    last_seen: Optional[str] = None     # ISO date of most recent run
    runs_30d: int = 0


@dataclass
class Agent:
    id: str
    display: str
    leader: str = ""                   # persona / who the agent is "after"
    theme_role: str = "agent"          # display label under the active theme
    is_coordinator: bool = False
    membership: str = "cabinet"        # cabinet | isolated
    status: str = "unknown"            # green | yellow | red | unknown
    last_run: str = ""
    goal_metric: str = ""
    bulletin: str = ""                 # short body/headline
    jobs: list[Job] = field(default_factory=list)
    skills: list["Skill"] = field(default_factory=list)   # declared skills (pinned + scoped)
    connectors: list[str] = field(default_factory=list)
    runs_30d: int = 0
    tokens_30d: int = 0                # summed from run-reports that carry usage (P2 telemetry)
    cost_30d: float = 0.0              # summed api-equiv $ over 30d (subscription: quota, not billed)
    appointed: str = ""               # ISO date the agent was appointed/created
    placeholder: str = ""              # set when the agent is planned, not established


@dataclass
class Gap:
    kind: str        # info | warn
    label: str


@dataclass
class Realm:
    name: str
    root: str
    theme_collective: str = "Realm"    # e.g. "Cabinet"
    theme_agent: str = "Agent"         # e.g. "Minister"
    theme_coordinator: str = "Coordinator"  # e.g. "Hand"
    theme_icon: str = "🏛️"
    engine: str = "Claude"
    generated_at: str = ""
    agents: list[Agent] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    sections: list = field(default_factory=list)   # user-promoted sections/artifacts: [{name, path|url}]

    @property
    def coordinator(self) -> Optional[Agent]:
        return next((a for a in self.agents if a.is_coordinator), None)

    @property
    def members(self) -> list[Agent]:
        return [a for a in self.agents if not a.is_coordinator]

    @property
    def tokens_30d(self) -> int:
        return sum(a.tokens_30d for a in self.agents)

    @property
    def cost_30d(self) -> float:
        return sum(a.cost_30d for a in self.agents)
