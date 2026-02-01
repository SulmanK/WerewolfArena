# Purple Agents

This folder holds purple agent implementations and helpers used for evaluation.

Quick paths:
- **NPC baseline**: `agents/npc_agent.py` (rule-based, deterministic)
- **A2A HTTP client**: `agents/a2a_agent.py`
- **Gemini proxy (optional runtime)**: `purple/proxies/a2a_gemini_proxy.py`

To add a new purple agent, implement `AgentBase` and register it in `agents/registry.py`,
or run your own A2A server and point the benchmark at it via `--a2a-endpoint`.
