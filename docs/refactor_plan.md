# Refactor Design Doc: Modular Agent Architecture

## Goals
- Make it easy to add or swap purple agents without touching game logic.
- Share common layers between green and purple agents (schema, protocol, logging, config).
- Reduce coupling between evaluation orchestration and agent implementations.
- Preserve current behavior and metrics while improving extensibility.
- Make it easy for contributors to fork this repo and add new purple agents to test.
- Clarify separation between green and purple agent code (directory boundaries).

## Non‑Goals
- Redesign metrics or game rules.
- Change benchmark outputs or leaderboard compatibility.
- Add new roles or gameplay mechanics (can be future work).

## Current Pain Points
- Agent implementations are spread across `agents/`, `scripts/`, and `green_agent/`.
- A2A schema and observation construction are duplicated across modules.
- The purple agent story isn’t clear for users who want to plug in their own agent.
- No explicit plugin/registry for agent implementations.

## Proposed Architecture

### 1) Shared Core Layer (new package: `core/`)
Create a small shared layer that both green and purple sides import.

**Responsibilities**
- A2A observation schema + validation
- Action schema (speak/vote/night_power) + validation
- Shared data types (roles, phases, game state)
- Common config parsing (env + CLI)
- Logging helpers (JSONL, manifest)

**Files**
```
core/
  schema.py        # obs/action schemas + validation
  types.py         # Role, Phase, Action, GameState
  config.py        # config dataclasses / parsing
  logging.py       # shared log helpers
```

### 2) Agent Interface (new package: `agents/` cleanup)
Formalize a single interface for any purple agent implementation.

**Proposed interface**
```
class AgentBase:
    def speak(self, obs: Observation) -> Action: ...
    def vote(self, obs: Observation) -> Action: ...
    def night_power(self, obs: Observation) -> Action: ...
```

**Implementations**
- `NpcAgent` (existing)
- `A2AAgent` (HTTP client wrapper)
- `LLMAgent` (optional: local provider, Gemini proxy)

### 3) Agent Registry / Factory
Expose a single entry point to build an agent by name or config.

```
agents/
  registry.py    # get_agent(name, config)
  npc_agent.py
  a2a_agent.py
  llm_agent.py   # optional
```

### 4) Green Agent Orchestration
Green agent should only orchestrate games and scoring.
It should *not* be responsible for constructing observations or actions.

Refactor:
- Move obs/action building into `core/schema.py`.
- Green agent passes `Observation` objects to agents.
- Scoring remains in `scorer/`.

### 5) Purple Agent Plug‑in Story
Provide a clear, documented path for user‑supplied agents:

Option A: **HTTP A2A** (default)
- Users run a server that implements the A2A action schema.
- The green agent calls it via `A2AAgent`.

Option B: **Python class** (advanced)
- Users implement `AgentBase` and register it in `agents/registry.py`.

## File/Module Changes (High‑Level)
- Add `core/` with shared schema/types/config.
- Replace `agents/a2a_adapter.py` with `agents/a2a_agent.py` and use shared schema.
- Update `benchmark/game.py` to use `AgentBase` and shared observation builder.
- Update `green_agent/server.py` to build observations via `core/schema.py`.
- Document the purple agent extension points in README.

## File Checklist
**New files**
- `core/types.py`
- `core/schema.py`
- `core/config.py`
- `core/logging.py`
- `agents/base.py`
- `agents/registry.py`
- `agents/a2a_agent.py`
- `agents/llm_agent.py` (optional)

**Modified files**
- `agents/npc_agent.py`
- `benchmark/game.py`
- `benchmark/agent_vs_npc.py`
- `green_agent/server.py`
- `purple/proxies/a2a_gemini_proxy.py` (optional validation reuse)
- `README.md`
- `docs/architecture.md`
- `docs/refactor_plan.md`

**Potential removals**
- `agents/a2a_adapter.py` (removed after migration)

**Planned structure changes**
- Create explicit directories for purple agents (e.g., `purple_agent/` or `agents/purple/`)
- Create explicit directories for green agent runtime (e.g., `green_agent/` already exists; tighten scope)
 - Move `scripts/a2a_gemini_proxy.py` to `purple/proxies/a2a_gemini_proxy.py`
 - Rename `agents/scripted.py` to clarify NPC role (now `agents/npc_agent.py`)

## Migration Plan
1) Add `core/` with schemas + types (no behavior changes).
2) Replace `agents/a2a_adapter.py` with `agents/a2a_agent.py`.
3) Update `game.py` to pass structured obs to agents.
4) Update green orchestration to rely on core schema.
5) Update README with “Add your agent” section.
6) Restructure directories to clearly separate green vs purple code.
7) Scan for deprecated patterns and clean them up.
8) Add “Contributing: add a purple agent in 3 steps” to README.

## Success Criteria
- A new purple agent can be added by creating one file + registering it.
- Green agent does not duplicate obs/action logic.
- Existing tests still pass and JSON output format is unchanged.

## Open Questions
- Do we want a formal plugin system (entry points), or a simple registry dict?
- Should the Gemini proxy live in `scripts/` or be a first‑class `LLMAgent`?
- Do we support per‑role endpoints or a single endpoint for all roles?
