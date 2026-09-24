# ARMADA — New-user onboarding & off-desktop comms (design)

> Status: **draft / not yet built.** Captured so it's ready to pick up.
> **Guiding tenet:** make it as frictionless as possible for the user. The **only** action we
> accept asking of them is signing in to their **paid Claude account** (a hard dependency known
> from the start). *Everything else that can be done behind the scenes, we do behind the scenes* —
> no manual Python/Node/npm/terminal steps, ever.

---

## 1. First-run setup (vanilla Windows + the ARMADA installer)

### What the installer does silently (no user action)
- Bundles the **Python runtime**, the **app**, and **pywebview** (frozen — the user never sees Python).
- Bundles / provisions **Node.js** + the **Claude Code CLI** (the engine).
- Detects the **Edge WebView2 runtime** and installs it if missing (Evergreen bootstrapper). Present
  by default on Windows 11, so usually a no-op.
- Registers Start-menu / desktop shortcuts and the app's own identity (AppUserModelID + icon).

### What the user consciously does — the whole journey
1. **Run the installer** — double-click → accept location → Install → finish.
2. **Launch ARMADA** — opens straight into a first-run setup screen.
3. **Sign in to Claude** — one button → browser OAuth into their existing **Claude Pro/Max** account
   → approve. The single credential step. No API key; nothing secret typed into ARMADA.
4. **See the green "You're ready" check** — the app runs its own preflight (engine present, signed
   in, WebView2 OK). Anything missing is shown with a one-click **Fix**.
5. **Create the first realm** — pick a template (State / Company / Crew / Scratch) or adopt an
   existing folder; name it; choose starter agents. *(Candidate to auto-do — see Open decisions.)*
6. **Done** — the cockpit opens.

Essentially: **install → launch → sign in to Claude → make a realm.** The Claude subscription is the
only true prerequisite the installer can't remove — surface that requirement on the download page and
again on the sign-in screen so nobody stalls at step 3.

### Open decisions (settle before building the installer)
- **Bundle vs fetch Node + Claude Code:** bundle = bigger download, offline-capable, most reliable;
  fetch-at-setup = smaller installer, needs internet on first run. *Lean: bundle*, per the tenet.
- **Auto-create a starter realm** on first run so even step 5 is optional (fastest "it works").
- **Update channel:** local builds have no git remote (see the Restart button work); decide how the
  packaged app self-updates (bundled updater vs signed release feed) separately from dev restart.

### Codebase gaps to close (currently hand-provisioned)
- No `pyproject.toml` / dependency manifest — add one declaring **pywebview** as an optional
  `[app]` extra (core stays stdlib-only).
- No installer / bootstrap — add a build pipeline (freeze the app, assemble the bundle, produce the
  Windows installer) and a first-run **setup route** in the app (the wizard behind steps 3–5).
- Preflight already exists as `matcap doctor`; the wizard reuses it for the green check.

---

## 2. Off-desktop communication channel → **Telegram**

**Decision: Telegram is the channel.** Free for us and the user, trivial bot setup, works from a
local app with no public server, rich interactive messages, cross-platform. Already used by the live
Cabinet (Development ministry price-watch → Telegram), so it's a proven fit.

### Why Telegram over the alternatives
- **Telegram Bot API** — free; **long-polling (`getUpdates`)** means the local app pulls messages
  over plain HTTPS, so **no public webhook / no NAT hole / no relay server**. Plain HTTPS = doable
  with **stdlib `urllib`**, so it adds **zero Python dependencies** (fits ARMADA's ethos). Supports
  inline buttons (perfect for approval prompts), files, and images. Generous single-user limits.
- **Signal** — no official bot API; `signal-cli` needs a dedicated number/linked device. High friction.
- **WhatsApp** — Business API is paid, Meta-gated, per-message priced. Fails "free/frictionless."
- **Discord** — free bot API, but server-oriented; 1:1 DMs are clunkier than Telegram.
- **Email** — universal but not real-time/interactive; good only for digests.
- **Push (ntfy/Pushover)** — simple but one-way notifications, weak for two-way commands.

### How we introduce it (architecture)
- Ship a **Telegram *bot*, not a CLI.** The bot IS the phone client — a user who only wants their
  phone gets the full remote (chat with agents, receive digests, approve/deny autonomy-gated actions
  via inline buttons) with no desktop needed. (A "Telegram CLI" like tdlib/`tg` exists but is for
  *user accounts* — the wrong tool here.)
- **Transport:** local app runs a background long-poll loop (`getUpdates`, ~30s timeout) → routes
  inbound messages to the right agent/thread through the existing engine → sends replies via
  `sendMessage`. Same runner/threads underneath as the desktop chat; Telegram is just another
  ingress/egress surface (aligns with the planned agent-behavior seams: messaging + ingress).
- **Opt-in, never required.** ARMADA is fully usable without it.

### Setup friction (and how we minimize it)
The one unavoidable step: each user runs their **own** bot (their token, their private chats — keeps
it local, no cloud on our side, we never hold their channel). To make it painless:
- A guided Settings screen: deep-link to **@BotFather** → user creates a bot (~1 min) → pastes the
  token into one field → taps **/start** on their new bot → ARMADA confirms the link with a test
  message. Store the token locally (same posture as other local secrets; never leaves the machine).
- We do **not** run a shared relay bot — that would mean holding a cloud channel + credentials,
  against the local/private ethos.

### Open questions for later
- Per-realm bot vs one bot across realms (with a realm switch command).
- Mapping Telegram chats → agents/threads (default coordinator? `/agent <name>` commands? one chat
  per agent?).
- Whether the installer can pre-seed anything to shave the BotFather step further (likely not without
  a relay; accept the ~1-min token step as the Telegram equivalent of the Claude sign-in).

### Verified (Sep 2026)
Telegram Bot API is free; `getUpdates` long-polling (positive timeout, e.g. 30s) keeps one connection
open and returns only on new updates — no webhook needed; incoming updates don't count against the
~30 msg/s send budget; undelivered updates are retained 24h.
