# `armada/routes/agents.py`

Agents, their threads and chat.

new/save/retire/reinstate/delete an agent, avatar management, thread listing/turns/rail/
truncate/new-thread/autoname, chat + chat-stream + chat-stop, run, reveal, job proposals.

Split out of serve.py (Phase 2, 2.3) — a pure move, no behaviour change; the route table
stays in serve.py, only the handler bodies moved.

### class `AgentRoutes`

—

- `AgentRoutes._get_chat_stop(self)` — —
- `AgentRoutes._get_retired_agents(self)` — Who could be brought back, and what they were. Feeds the Appoint modal's Reinstate tab, which fills its form from this rather than making anyone retype a settled agent.
- `AgentRoutes._get_new_agent(self)` — —
- `AgentRoutes._get_agent(self, path)` — —
- `AgentRoutes._get_embed_thread(self)` — —
- `AgentRoutes._get_threads(self)` — —
- `AgentRoutes._get_proposals_count(self)` — —
- `AgentRoutes._get_agent_activity(self)` — Live activity state per agent ({id: 'working'|'input'|'unseen'|'idle'}) so the dashboard can refresh the status dots without a full reload.
- `AgentRoutes._get_thread_turns(self)` — —
- `AgentRoutes._get_thread_rail(self)` — —
- `AgentRoutes._get_avatar(self, path)` — —
- `AgentRoutes._get_thread_file(self)` — —
- `AgentRoutes._new_agent(self, body: dict)` — —
- `AgentRoutes._upload_avatar(self, body: dict)` — —
- `AgentRoutes._set_avatar_preset(self, body: dict)` — —
- `AgentRoutes._agent_retire(self, body: dict)` — —
- `AgentRoutes._agent_reinstate(self, body: dict)` — —
- `AgentRoutes._agent_delete(self, body: dict)` — —
- `AgentRoutes._chat_stream(self, q: dict)` — Server-Sent Events: stream the agent's intermediate steps for one chat turn.
- `AgentRoutes._chat_stop(self, q: dict)` — —
- `AgentRoutes._thread_truncate(self, body: dict)` — Keep only the first `keep` messages of a thread (drops the rest) — powers 'restart from here' and 'edit': the caller then re-sends the (possibly edited) message.
- `AgentRoutes._threads_list(self, agent: str)` — —
- `AgentRoutes._thread_action(self, body: dict)` — —
- `AgentRoutes._delete_thread_artifacts(self, agent: str, slug: str)` — Delete the output-artifact files a thread produced (paths recorded in its turns). Only touches files INSIDE the realm — never anything outside it. Best-effort.
- `AgentRoutes._new_thread(self, body: dict)` — —
- `AgentRoutes._autoname_thread(self, agent: str, thread: str, first_msg: str)` — After the first exchange, give a still-default 'New Chat' thread a title derived from the prompt (like the Claude app). Only touches auto-named 'new-chat*' threads that the owner hasn't renamed; returns the new title or None. The owner can still rename afterwards.
- `AgentRoutes._remove_avatar(self, body: dict)` — —
- `AgentRoutes._save_agent(self, body: dict)` — —
- `AgentRoutes._job_proposal(self, body: dict)` — Approve or reject an agent-authored pending job proposal (owner action).
- `AgentRoutes._chat(self, body: dict)` — —
