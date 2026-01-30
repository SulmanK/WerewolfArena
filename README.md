# AgentBeats Green - Werewolf Benchmark

## Run a single game

```
python -m benchmark.runner --seed 123 --max-turns 4 --max-rounds 4 --output fixtures/golden_score.json --log-jsonl fixtures/sample_log.jsonl
```

## Run multiple seeds and aggregate

```
python -m benchmark.multi --seeds-file configs/seeds.txt --max-turns 4 --max-rounds 4 --output fixtures/aggregate.json
```

## Tests

```
python -m pytest scorer/tests/test_score.py benchmark/tests/test_protocol.py
```

## Structure
- configs/: task/config seeds (placeholders).
- benchmark/: game engine, runner, multi-seed aggregator, protocol, logging, (stub) A2A server.
- agents/: scripted baseline and stubs for A2A/LLM.
- scorer/: metrics and aggregation.
- fixtures/: sample log/score outputs.
- docker/: Dockerfile and entrypoint stub.
- scripts/: CI smoke script.

## Notes
- Current default is offline scripted baseline; A2A server/adapter are stubs (HTTP echo + scripted response).
- Online mode (opt-in): start an A2A endpoint (e.g., `python scripts/a2a_gemini_proxy.py` with `GEMINI_API_KEY`) and run with `--a2a-endpoint http://localhost:8080`. Default proxy model: `gemini-2.5-flash-lite`; override with `--model`.
- Agent vs NPC mode: add `--a2a-seats` or `--a2a-roles` to route only selected seats/roles to A2A; all others remain scripted.
- Proxy logging: set `LOG_FULL_PROMPT=1` to log full prompts; otherwise logs show a prompt hash + length.
- Proxy log files: use `--log-dir logs` to write a new timestamped log file each run.
- Dockerfile installs requirements.txt if present; adjust as we add deps.
- Stub A2A server: `python -m benchmark.a2a_server` (returns scripted actions); HTTP client stub in `agents/a2a_adapter.py`.
- Safety heuristics are simple keyword/regex checks; no external services or classifiers.
- CI smoke: `python scripts/ci_smoke.py` or `make ci`.
- Optional A2A mode: pass `--a2a-endpoint http://host:port` to runner; actions will be fetched from that endpoint per observation (scripted fallback if no endpoint).
- Metrics: vote accuracy/focus, misvotes, flip rates, survival, and soft safety flags as proxies for deception/detection; aligned with paper emphasis (win/loss and voting behavior).
- Agent vs NPC logs include `agent_seat`, `agent_role`, `game_index`, and `seed` in each JSONL record; `manifest.json` maps game index to seed/role.

## Purple agent contract (A2A)
Your evaluated agent is an A2A endpoint that receives observations and returns a single JSON action:
- **Endpoint**: `POST /` (JSON body).
- **Required response**: `{"type": "speak|vote|night_power", "content"?: "...", "target"?: "Name"}`
- **Inputs**: role, phase, remaining players, graveyard, debate so far, private info (if any).
- **Stateless**: the green agent provides all needed state each turn.

To swap models, point the A2A endpoint at a different model implementation (e.g., Gemini, OpenAI, local), and keep the same input/output JSON schema.

## Demo script outline (for video)
1) Build/run: `python -m benchmark.runner --seed 123 --max-turns 4 --max-rounds 4 --output fixtures/golden_score.json --log-jsonl fixtures/sample_log.jsonl`
2) Show scorecard JSON and tail JSONL log.
3) Optional: `python -m benchmark.a2a_server` (stub) and run with `--a2a-endpoint http://localhost:8080` to illustrate A2A wiring.
4) Multi-seed aggregate: `python -m benchmark.multi --seeds-file configs/seeds.txt --output fixtures/aggregate.json`

## Make targets
```
make run    # run a seeded game and write outputs
make smoke  # run minimal tests
make multi  # run multiple seeds and aggregate
make ci     # run smoke across seeds
```

## Quick setup and demo (offline default, optional API mode)
1) Install deps: `pip install -r requirements.txt`
2) Offline run (default, no keys needed):  
   `python -m benchmark.runner --seed 123 --max-turns 4 --max-rounds 4 --output fixtures/golden_score.json --log-jsonl fixtures/sample_log.jsonl`
3) Multi-seed aggregate:  
   `python -m benchmark.multi --seeds-file configs/seeds.txt --max-turns 4 --max-rounds 4 --output fixtures/aggregate.json`
4) Optional A2A/LLM mode (once you have an A2A endpoint, e.g., Gemini proxy):  
   - Set provider env (e.g., `GEMINI_API_KEY=...`) in your proxy.  
   - Run the proxy: `python scripts/a2a_gemini_proxy.py --model gemini-2.5-flash-lite --host 0.0.0.0 --port 8080`.  
   - Run benchmark with delegation:  
     `python -m benchmark.runner --seed 123 --max-turns 4 --max-rounds 4 --a2a-endpoint http://localhost:8080 --output fixtures/gemini_score.json --log-jsonl fixtures/gemini_log.jsonl`  
   - Agent vs NPC (single seat):  
     `python -m benchmark.runner --seed 123 --max-turns 4 --max-rounds 4 --a2a-endpoint http://localhost:8080 --a2a-seats Hayley --output fixtures/gemini_score.json --log-jsonl fixtures/gemini_log.jsonl`  
   - Agent vs NPC (by role):  
     `python -m benchmark.runner --seed 123 --max-turns 4 --max-rounds 4 --a2a-endpoint http://localhost:8080 --a2a-roles Werewolf --output fixtures/gemini_score.json --log-jsonl fixtures/gemini_log.jsonl`  
   - Agent vs NPC (role-balanced 40 games):  
     `python -m benchmark.agent_vs_npc --a2a-endpoint http://localhost:8080 --num-games 40 --shuffle-seed 2026 --output fixtures/agent_vs_npc_40.json --log-dir fixtures/agent_vs_npc_logs`  
   - Agent vs NPC (quick 12 games):  
     `python -m benchmark.agent_vs_npc --a2a-endpoint http://localhost:8080 --num-games 12 --shuffle-seed 2026 --output fixtures/agent_vs_npc_12.json --log-dir fixtures/agent_vs_npc_logs`  
   - Agent vs NPC (preset):  
     `python -m benchmark.agent_vs_npc --a2a-endpoint http://localhost:8080 --preset 12 --shuffle-seed 2026 --output fixtures/agent_vs_npc_12.json --log-dir fixtures/agent_vs_npc_logs`  
   - Agent vs NPC (role split override):  
     `python -m benchmark.agent_vs_npc --a2a-endpoint http://localhost:8080 --num-games 12 --role-weights werewolf=3,seer=3,doctor=3,villager=3 --shuffle-seed 2026 --output fixtures/agent_vs_npc_12.json --log-dir fixtures/agent_vs_npc_logs`  
   - Agent vs NPC (metrics sanity check for first 3 games):  
     `python -m benchmark.agent_vs_npc --a2a-endpoint http://localhost:8080 --num-games 12 --shuffle-seed 2026 --sanity-check 3 --output fixtures/agent_vs_npc_12.json --log-dir fixtures/agent_vs_npc_logs`  
   - Multi-game output is written in a summary JSON format (status, num_games, performance_metrics, roles_played, advanced_metrics).
   - `performance_metrics.irs` and `performance_metrics.vrs` map to IRP and VSS (paper-inspired, heuristic).
   - Per-game logs include `agent_seat` and `agent_role`; summary records include `roles`. `manifest.json` in the log dir maps game index to seed/role.
   - Note: offline scripted remains the default; API mode is opt-in.
   - To load `.env` automatically: `python -m dotenv run -- python scripts/a2a_gemini_proxy.py --model gemini-2.5-flash-lite --host 0.0.0.0 --port 8080`.


Commands

- python -m dotenv run -- python scripts/a2a_gemini_proxy.py --model gemini-2.5-flash-lite --host 0.0.0.0 --port 8080 --log-dir logs

- python -m benchmark.agent_vs_npc --a2a-endpoint http://localhost:8080 --num-games 12 --sanity-check 12 --shuffle-seed 20206 --output fixtures/agent_vs_npc_12.json --log-dir fixtures/agent_vs_npc_logs


- build out agents: docker compose -f infra/docker-compose.agentbeats.yml up --build --abort-on-container-exit

- Pushed to GCR
docker build -t agentbeats_green_agent -f infra/Dockerfile.green .
docker build -t agentbeats_purple_agent -f infra/Dockerfile.purple .
docker tag agentbeats_green_agent ghcr.io/sulmank/agentbeats-green:latest
docker tag agentbeats_purple_agent ghcr.io/sulmank/agentbeats-purple:latest
docker push ghcr.io/sulmank/agentbeats-green:latest
docker push ghcr.io/sulmank/agentbeats-purple:latest


