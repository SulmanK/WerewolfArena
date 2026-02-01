## Deployment Design Doc: Purple Agent + Green Evaluator (AgentBeats + Leaderboard)

### Goal
Deploy a purple agent (player) and green agent (evaluator) to AgentBeats and submit to the leaderboard with a reproducible, testable pipeline.

### Scope
- Build Docker images for purple + green
- Run local integration test via docker-compose
- Push images to registry (GHCR)
- Register purple agent on AgentBeats
- Submit scenario to leaderboard repo

### Non-Goals
- Model training or strategy changes
- Metrics redesign
- Multi-cluster scaling

---

## System Overview

### Green agent (evaluator)
- Orchestrates games, runs NPCs, computes metrics.
- A2A server on port 9009.
- Uses Gemini via A2A proxy for the evaluated agent seat (`purple/proxies/a2a_gemini_proxy.py`).
- Requires `GEMINI_API_KEY` for the Gemini proxy.

### Purple agent (player)
- A2A server on port 8100.
- Receives game messages and returns actions.
- Can be LLM-backed; in this codebase the tested agent seat is routed to the Gemini proxy.

### Data flow
```
AgentBeats -> Green (A2A) -> Purple (A2A) + NPCs -> Results -> Leaderboard
```

---

## Required Artifacts
- Docker image: green agent
- Docker image: purple agent
- AgentBeats registration: purple image URL + agentbeats_id
- Leaderboard PR: scenario.toml referencing green + purple images

---

## Configuration

### Environment variables
Green:
- GEMINI_API_KEY (required for Gemini proxy)
- GREEN_AGENT_HOST (default 0.0.0.0)
- GREEN_AGENT_PORT (default 9009)
- LOG_LEVEL (default INFO)

Purple:
- If the purple agent uses an LLM provider, set its provider key (not required for the scripted baseline).
- AGENT_ID (optional; default baseline-agent)
- AGENT_PORT (default 8100)

### Game config (AgentBeats scenario)
```
num_tasks = 5         # games
num_players = 8
enable_sheriff = true
```

---

## Docker Images

### Current repo gap
This repo includes green/purple Dockerfiles and a docker-compose test stack (under `infra/`).

### Required files (to match the intended setup)
- `infra/Dockerfile.green`
- `infra/Dockerfile.purple`
- `infra/docker-compose.agentbeats.yml`
- `infra/run_agentbeats_docker.py` (runner entrypoint for AgentBeats local run)

We should mirror the layout from the intended reference repo (green + purple agents and compose test).

---

## Local Validation (pre-deploy)

0) Ensure Dockerfiles + compose exist (see “Required files to add”).

1) Build images
```
docker build -t local-green -f infra/Dockerfile.green .
docker build -t local-purple -f infra/Dockerfile.purple .
```

2) Run Gemini proxy (A2A endpoint)
```
python purple/proxies/a2a_gemini_proxy.py --host 0.0.0.0 --port 8080 --model gemini-2.5-flash-lite
```

3) Run integration test
```
docker-compose -f infra/docker-compose.agentbeats.yml up --abort-on-container-exit
```

4) Verify results
- `results/agentbeats_docker_results.json`
- Check metrics, roles_played, and completion count.

---

## Bring This Repo Up to AgentBeats-Ready (Implementation Steps)

1) Add green + purple agent servers (A2A):
   - Green: orchestrator + metrics export.
   - Purple: player agent server.

2) Add Dockerfiles:
   - `infra/Dockerfile.green`: installs deps and runs green server on 9009.
   - `infra/Dockerfile.purple`: installs deps and runs purple server on 8100.

3) Add docker-compose for local test:
   - `infra/docker-compose.agentbeats.yml` with purple + green services.

4) Add runner script:
   - `infra/run_agentbeats_docker.py` to execute a one-shot eval and emit results JSON.

5) Update README with “Online/AgentBeats mode” instructions.

---

## Publish to Registry (GHCR example)

1) Tag and push
```
docker tag local-green ghcr.io/YOUR_USER/green-agent:latest
docker tag local-purple ghcr.io/YOUR_USER/purple-agent:latest

echo $GITHUB_TOKEN | docker login ghcr.io -u YOUR_USER --password-stdin
docker push ghcr.io/YOUR_USER/green-agent:latest
docker push ghcr.io/YOUR_USER/purple-agent:latest
```

---

## AgentBeats Registration

1) Register purple image on AgentBeats.
2) Record `agentbeats_id`.

---

## Leaderboard Submission

### Repo Strategy
- **This repo**: your agent code + Docker builds.
- **Leaderboard repo**: separate fork used only to submit `scenario.toml` via PR.
- If you want to keep everything in one monorepo, you can **vendor the leaderboard repo as a Git submodule**, but the actual submission still must go through a PR to the leaderboard repository.

### AgentBeats Tutorial Mapping (Gemini)
The official tutorial steps apply directly with these substitutions:
- Use `GEMINI_API_KEY` instead of `OPENAI_API_KEY`.
- Your results JSON uses IRP/VSS/KRE and heuristic voting metrics, so leaderboard queries should reference those fields.

Tutorial link (reference):
```
https://docs.agentbeats.dev/tutorial/
```

Example `scenario.toml` (Gemini):
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

Example leaderboard query for this repo’s results:
```
[
  {
    "name": "Overall Performance",
    "query": "SELECT\n  id,\n  ROUND(AVG(r.result.performance_metrics.win_rate), 3) AS \"Win Rate\",\n  ROUND(AVG(r.result.performance_metrics.irs), 3) AS \"IRP\",\n  ROUND(AVG(r.result.performance_metrics.vrs), 3) AS \"VSS\",\n  ROUND(AVG(r.result.advanced_metrics.avg_kre), 3) AS \"KRE\"\nFROM results t\nCROSS JOIN UNNEST(t.results) AS r(result)\nGROUP BY id\nORDER BY \"Win Rate\" DESC, \"IRP\" DESC;"
  }
]
```

1) Fork leaderboard repo.
2) Edit `scenario.toml`:
```
[green_agent]
image = "ghcr.io/YOUR_USER/green-agent:latest"
env = { GEMINI_API_KEY = "${GEMINI_API_KEY}" }

[[participants]]
agentbeats_id = "YOUR_AGENT_ID"
image = "ghcr.io/YOUR_USER/purple-agent:latest"
name = "agent"
env = { GEMINI_API_KEY = "${GEMINI_API_KEY}" }

[config]
num_tasks = 5
```

3) Add GitHub secret `GEMINI_API_KEY`.
4) Push + PR.

---

## Metrics (Current Codebase)

This repo’s scorer is heuristic and *not* the same as the long README you provided:
- Vote accuracy and misvotes
- Flip rates (villagers toward wolves, wolves toward villagers)
- Survival rates (wolf/villager)
- Seer discovery rate, doctor protection rate
- Werewolf survival score
- IRP (identity recognition proxy from debate claims)
- VSS (vote skill score on critical votes)
- KRE (key-role effectiveness)
- Safety flags (toxic / pii / invalid_action)

Aggregation maps:
- `performance_metrics.irs` → `avg_irp`
- `performance_metrics.vrs` → `avg_vss`

## Risks and Mitigations

- **Rate limits / timeouts**: Keep `num_tasks` small for first run; raise later.
- **Missing API keys**: Validate envs via health checks and startup logs.
- **Agent card not reachable**: Verify `/.well-known/agent-card.json`.
- **Wrong ports**: Ensure 8100 for purple and 9009 for green in Dockerfiles.

---

## Validation Checklist

- [ ] Green image builds and passes healthcheck
- [ ] Purple image builds and passes healthcheck
- [ ] Local docker-compose run completes and writes results
- [ ] Images pushed to registry
- [ ] AgentBeats registration complete (agentbeats_id recorded)
- [ ] Leaderboard PR created with scenario.toml

---

## Open Questions
Resolved:
- Registry: GHCR
- Purple agent model/provider: Google Gemini Flash 2.5
- Leaderboard run size: `num_tasks = 40`
