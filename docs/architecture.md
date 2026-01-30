# Architecture and Design Notes

## Purpose
This document summarizes how the AgentBeats green evaluator and purple agent are
packaged in this repo, how data flows, and how reproducibility is handled.

## System overview
Components:
- Green agent (evaluator): A2A server that orchestrates games and emits results.
- Purple agent (player): A2A server that responds with actions (speak/vote/night_power).
- Gemini proxy (optional): A2A-compatible proxy that calls Gemini and returns actions.
- Benchmark engine: Game rules, logging, and scoring.

Data flow:
AgentBeats -> Green (A2A) -> Purple (A2A) + NPCs -> Results -> Leaderboard

## Key modules
- `green_agent/server.py`: A2A server that runs `benchmark.agent_vs_npc` and returns results.
- `benchmark/agent_vs_npc.py`: Role-balanced schedule, seeded games, aggregate metrics.
- `benchmark/game.py`: Seeded game logic, role assignment, voting, and state transitions.
- `scripts/a2a_gemini_proxy.py`: Optional Gemini proxy for A2A actions.
- `scorer/`: Metric calculation and aggregation.
- `infra/`: Dockerfiles and local compose test stack.

## Determinism and reproducibility
Deterministic elements:
- Role assignment and tie-breaking use seeded RNG.
- Game schedules are shuffled with `shuffle_seed`.
- Per-game seeds are generated from a seed list or `seed_start`.

Sources of nondeterminism:
- Remote LLM responses (Gemini) can vary across runs.
- Container tags like `:latest` can drift over time.

Mitigations:
- Fix `shuffle_seed` and `seed_start` for runs.
- Use deterministic sampling in the Gemini proxy (enabled by default).
- Pin images to specific tags or digests for leaderboard submissions.

## Results format
Output JSON includes:
- `performance_metrics`: win_rate, sr, irs, vrs, games_won, games_survived
- `advanced_metrics`: flip rates, seer discovery, doctor protection, kre/irp/vss
- `roles_played`: distribution across roles

Per-game logs (JSONL) and a `manifest.json` are emitted when log dir is enabled.

## Deployment model
Local:
- Run the Gemini proxy (optional)
- Run `benchmark.agent_vs_npc` directly or via Docker compose

AgentBeats:
- Push green and purple images to registry
- Register both on AgentBeats
- Submit `scenario.toml` to leaderboard repo and merge PR

## References
- `docs/deployment_design.md`
- `docs/design.md`
- `docs/design_agent_vs_npc.md`
