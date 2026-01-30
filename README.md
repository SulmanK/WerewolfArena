# AgentBeats Green - Werewolf Social Reasoning Benchmark

A reproducible social deduction benchmark for evaluating agents using the Werewolf game.
This repo provides a green evaluator (A2A server) and a purple agent (A2A player), plus
local and Docker workflows for AgentBeats submissions.

## What this benchmark evaluates
This benchmark focuses on social reasoning in multi-agent settings:
- Strategic reasoning under uncertainty
- Deception and persuasion (wolves vs villagers)
- Resistance to manipulation
- Multi-step planning across rounds

## How it works
Your purple agent plays Werewolf against NPCs. The green agent runs games, records logs,
and computes aggregate metrics. Results are emitted as JSON and can be submitted to the
leaderboard repo.

Data flow:
AgentBeats -> Green (A2A) -> Purple (A2A) + NPCs -> Results -> Leaderboard

## Metrics (current implementation)
This repo uses deterministic heuristics and aggregate scoring (no external judge):
- Win rate, survival rate
- Vote accuracy, misvote rate, flip rates
- Seer discovery rate, doctor protection rate
- IRP (identity recognition proxy), VSS (vote skill score), KRE (key role effectiveness)
- Safety flags (toxic, pii)

See details in `docs/deployment_design.md` and `docs/design.md`.

## Reproducibility note
Game mechanics are seeded (role assignment, order, tie-breaking). If you use an external
LLM (Gemini proxy), outputs can still vary slightly across runs. For best stability:
- Keep `shuffle_seed` fixed
- Pin images/tags
- Use deterministic proxy settings (enabled by default in `scripts/a2a_gemini_proxy.py`)

## Quickstart (local)
Single game:
```
python -m benchmark.runner --seed 123 --max-turns 4 --max-rounds 4 --output fixtures/golden_score.json --log-jsonl fixtures/sample_log.jsonl
```

Multi-seed aggregate:
```
python -m benchmark.multi --seeds-file configs/seeds.txt --max-turns 4 --max-rounds 4 --output fixtures/aggregate.json
```

Agent vs NPC (role-balanced):
```
python -m benchmark.agent_vs_npc --a2a-endpoint http://localhost:8080 --num-games 12 --shuffle-seed 20206 --output fixtures/agent_vs_npc_12.json --log-dir fixtures/agent_vs_npc_logs
```

## Tested commands (local)
```
python -m dotenv run -- python scripts/a2a_gemini_proxy.py --model gemini-2.5-flash-lite --host 0.0.0.0 --port 8080 --log-dir logs
python -m benchmark.agent_vs_npc --a2a-endpoint http://localhost:8080 --num-games 12 --sanity-check 12 --shuffle-seed 20206 --output fixtures/agent_vs_npc_12.json --log-dir fixtures/agent_vs_npc_logs
```

## Docker (local integration)
Requires a local `.env` file with your Gemini key:
```
GEMINI_API_KEY=your_key_here
```

```
docker compose -f infra/docker-compose.agentbeats.yml up --build --abort-on-container-exit
```

## Testing your agent (local)
1) Build your purple agent image.
```
docker build -t my-purple-agent -f infra/Dockerfile.purple .
```

2) Update compose to point to your purple image (in `infra/docker-compose.agentbeats.yml`).

3) Run the evaluation.
```
docker compose -f infra/docker-compose.agentbeats.yml up --abort-on-container-exit
```

4) Check results.
```
cat results/agentbeats_docker_results.json | jq .performance_metrics
```

Expected output format (shape):
```
{
  "status": "complete",
  "num_games": 12,
  "games_completed": 12,
  "performance_metrics": {
    "irs": 0.0,
    "vrs": 0.0,
    "sr": 0.0,
    "win_rate": 0.0,
    "games_survived": 0,
    "games_won": 0,
    "total_games": 12
  },
  "roles_played": {
    "werewolf": 0,
    "villager": 0,
    "seer": 0,
    "doctor": 0
  },
  "advanced_metrics": {
    "avg_kre": 0.0,
    "avg_irp": 0.0,
    "avg_vss": 0.0,
    "safety_counts": {
      "toxic": 0,
      "pii": 0
    }
  }
}
```

## Build and push images (GHCR)
```
docker build -t agentbeats_green_agent -f infra/Dockerfile.green .
docker build -t agentbeats_purple_agent -f infra/Dockerfile.purple .
docker tag agentbeats_green_agent ghcr.io/sulmank/agentbeats-green:latest
docker tag agentbeats_purple_agent ghcr.io/sulmank/agentbeats-purple:latest
docker push ghcr.io/sulmank/agentbeats-green:latest
docker push ghcr.io/sulmank/agentbeats-purple:latest
```

## Deployment to AgentBeats
Step 1: Build and push images (see GHCR section above).

Step 2: Register on AgentBeats
- Go to agentbeats.dev
- Register green and purple agents
- Copy both `agentbeats_id` values

Step 3: Submit to leaderboard
- Fork the leaderboard repo
- Add GitHub Actions secret: `GEMINI_API_KEY`
- Update `scenario.toml`:
```
[green_agent]
agentbeats_id = "YOUR_GREEN_ID"
env = { GEMINI_API_KEY = "${GEMINI_API_KEY}" }

[[participants]]
agentbeats_id = "YOUR_PURPLE_ID"
name = "agent"
env = { GEMINI_API_KEY = "${GEMINI_API_KEY}" }

[config]
num_tasks = 40
```
- Commit/push, open PR, merge

## AgentBeats submission (leaderboard repo)
1) Register green and purple agents on AgentBeats.
2) Fork the leaderboard repo and edit `scenario.toml`.
3) Push and open a PR; merge to update the leaderboard.

Example `scenario.toml`:
```
[green_agent]
agentbeats_id = "YOUR_GREEN_ID"
env = { GEMINI_API_KEY = "${GEMINI_API_KEY}" }

[[participants]]
agentbeats_id = "YOUR_PURPLE_ID"
name = "agent"
env = { GEMINI_API_KEY = "${GEMINI_API_KEY}" }

[config]
num_tasks = 40
```

## A2A contract (purple agent)
Endpoint:
- `GET /.well-known/agent-card.json`
- `POST /` with JSON body

Expected response schema:
```
{"type": "speak|vote|night_power", "content"?: "...", "target"?: "Name"}
```

## Repo map
- `benchmark/` game engine, runner, A2A protocol, logs
- `green_agent/` A2A green evaluator server
- `agents/` scripted baselines and adapters
- `scorer/` metrics and aggregation
- `infra/` Dockerfiles and compose
- `scripts/` Gemini proxy and helpers
- `docs/` design and deployment docs

## Docs
- `docs/deployment_design.md`
- `docs/design.md`
- `docs/design_agent_vs_npc.md`

## Tests
```
python -m pytest scorer/tests/test_score.py benchmark/tests/test_protocol.py
```
