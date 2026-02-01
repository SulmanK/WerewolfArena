# AgentBeats Green Design Doc - Werewolf Social Reasoning Benchmark

## 1) Goals & Scope (Green Phase)
- Deliver a reproducible Werewolf social-reasoning benchmark as the Green agent submission, aligned with Werewolf Arena (arxiv:2407.13943) and A2A.
- Focus only on the Werewolf track for Phase 1; defer other tracks to later phases.

## 2) Submission Requirements (Phase 1 Checklist)
- Abstract: 3-5 sentences describing the tasks and metrics of the Werewolf benchmark.
- Public GitHub repo: Source + README with overview, setup, A2A usage, run commands.
- Baseline purple agents: A2A-compatible scripted/naive baselines with expected scores.
- Docker image: End-to-end run without manual intervention; offline by default.
- AgentBeats registration: Register green agent and baselines on the platform (when live).
- Demo video: <=3 minutes showing a seeded run, scorecard, and a flagged violation/success.

## 3) Judging Criteria Alignment
- Technical correctness & quality: clean code, typed configs, clear README, robust logging/error handling, sensible resource use, correct task logic and scoring.
- Reproducibility: deterministic seeds, pinned deps, fixed fixtures/configs, consistent outputs across runs.
- Benchmark design quality: realistic social-deception tasks, meaningful difficulty via role mixes/utterance caps, avoids trivial heuristics.
- Evaluation methodology: objective scorer, automated, multi-dimensional metrics (success, deception, safety, efficiency), beyond pass/fail.
- Innovation & impact: extends Werewolf Arena with reproducible A2A packaging, stronger safety/policy checks, clearer baselines, and deterministic CI/Docker flow.

## 4) Alignment with Paper/Repo and Enhancements
- Preserve core protocol: roles, day/night order, voting/elimination, termination (wolves parity or all dead), utterance/turn limits, seeded role assignment.
- Parity targets: match role/action sets and phase timing from the paper and our fork `werewolf_arena-main`.
- Enhancements: deterministic seed list and published configs; richer scorecard (deception success, persuasion robustness, safety violations); offline Docker runner; CI smoke games; A2A schema and validation; optional safety-aware baseline.
- Any deviations from the paper are documented in README and scorer docs.

## 4.1) Paper Deep Dive and Planned Adjustments
- Paper baseline protocol (per repo/paper): 8 players; roles = 2 Werewolves, 1 Seer, 1 Doctor, rest Villagers; max debate turns = 8; bidding determines next speaker; synthetic votes can be injected; win when wolves reach parity or die out; night (eliminate/protect/unmask) -> day debate/vote -> summaries.
- Current repo gaps vs. AgentBeats needs: no deterministic seeding (random.sample/shuffle without a fixed seed), remote LM calls (OpenAI/Gemini) so not offline, no A2A schema, no scoring/metrics beyond win/loss, limited safety signals, and concurrency introduces nondeterminism.
- Planned changes: fix seeds globally (role assignment, bidding, speaker choice); remove/disable network in Docker and use local scripted/LM baselines; add explicit scorecard (win rate, vote accuracy, deception success, persuasion robustness, safety violations, efficiency); enforce utterance/action caps in config; log JSONL with violations; publish configs/fixtures; add A2A contract; add CI smoke runs; document any departures (e.g., if we cap turns lower for CI or tweak synthetic votes).
 - Metrics track vote accuracy/focus, misvotes, flip rates, survival, and soft safety flags as proxies for deception/detection; no heavy classifiers (paper-aligned).

## 4.2) AgentBeats A2A Compatibility (inspired by tau-bench green agent blog)
- Agent interface: define an `AgentInterface` abstraction with implementations: (a) NpcAgent (rule-based bids/debate/votes/night actions), (b) LocalModelAgent (optional, points to a local model server), (c) A2AAgent adapter (sends A2A requests to an external agent). Docker default = scripted only, offline.
- A2A schema: observation payload includes public chat transcript, role card, graveyard, round/phase, remaining players, and private info (other wolf if role). Actions: `speak{text}`, `vote{target}`, `night_power{target}`. Include step budget and seed in request. Provide curl examples.
- Determinism: seed Python `random` and any model sampling; seed order for player names, bids, speaker selection. Constrain utterance length and turn caps in config; enforce determinism in parallelism (optionally disable threads or use ordered execution).
- Runner contract: `python -m benchmark.run --track werewolf --seed 123 --output scores.json` maps each game tick to A2A requests when A2A mode is on; scripted agents used otherwise.
- Offline packaging: Docker image contains fixtures/configs, scripted baselines, scorer; network blocked by default. Local model server optional but off by default.
- Scoring/logging: per-game JSON scorecard; JSONL step logs with violations and actions; aggregation across seeds. Mirrors the "agentify the assessment" pattern from the tau-bench blog.

## 4.3) Learnings from AgentBeats blogs & tau-bench agentify example
- Architecture pattern: separate assessment manager (green) from evaluated agents (purple); use a launcher to coordinate runs, similar to tau-bench’s `launcher.py` pattern.
- Directory/entrypoint pattern: keep `launcher`/`main` driving evaluation, config-driven; include `agents/` (baselines), `configs/` (tasks/seeds), `scorer/`, `docs/`. Mirror the tau example so users recognize the layout.
- Protocol: follow A2A request/response lifecycle (obs/actions schema, step budget, seed) as shown in the tau-bench example; provide a simple HTTP or CLI bridge that can talk to external A2A agents while defaulting to offline scripted ones.
- Determinism and offline defaults: unlike the tau example’s remote LM usage, default to scripted/local agents; make `.env` optional; fail closed on missing keys; document how to opt-in to external models only outside Docker.
- Repro artifacts: sample commands, seed list, golden outputs, and small fixtures (akin to tau-bench example) to prove determinism and provide quick-start runs.

## 5) Task Design
- Deterministic games with fixed seeds and published configs (player/role counts, utterance caps, timers).
- Phases: Day chat -> Vote -> Night actions -> Resolution; enforce action legality and turn order.
- Fixtures: short games for CI and full-length evaluation suites.
- Agent vs NPC baseline mode: see `docs/design_agent_vs_npc.md`.

## 6) Evaluation & Scoring
- Core metrics: win rate by role, vote accuracy (wolves identified by day N), deception success/failure (wolves causing misvotes), persuasion robustness (villager flip rate after misleading statements), efficiency (turns/steps to resolution).
- Safety/policy: rule adherence (no illegal night talk), consistency (no self-contradictory role claims), toxicity/PII/policy violations.
- Outputs: per-game JSON scorecards; aggregate across seeds with deterministic weighting. Scorer has unit tests and golden fixtures.

## 7) A2A Integration & Reproducibility
- A2A schema: observations (public chat, role card, graveyard), actions (speak, vote, night power), step budget, seed.
- Provide sample curl and expected responses; log JSONL per turn (phase, role, utterance, action, result, violations).
- Determinism: seed all randomness (role assignment, ordering); cap tokens/utterances; disable external network in Docker.

## 8) Baseline Purple Agents
- Scripted: random speaker; basic villager/werewolf scripts; optional safety-aware script.
- Naive LLM-prompt baseline (text-only) for comparison. Publish expected baseline scores per seed.

## 9) Packaging & Runtime
- CLI: `python -m benchmark.run --track werewolf --seed 123 --output scores.json` (headless).
- Docker: single image with fixtures and baselines; entrypoint runs full eval suite; offline by default.
- Repo additions: `docs/`, `configs/` (game configs + seed list), `fixtures/` (example logs), `scorer/` (scoring + tests), `agents/` (baselines), `docker/` (Dockerfile/entrypoint).

## 10) Testing & CI
- Unit tests: scorer, protocol checks (illegal actions, phase transitions), A2A schema validation.
- Smoke tests: 1-2 seeded games in CI; assert deterministic scorecard shape/values.
- Lints/format as available.

## 11) Demo Video (<=3 min)
- Show rule overview, run Docker once, display scorecard, highlight a logged violation or correct vote.

## 12) Milestones
1) Protocol lock: confirm rules/roles/phase order and document any deviations.
2) Configs/seeds: publish seed list and game configs; add fixtures for tests.
3) Scorer: implement metrics + unit tests with golden outputs.
4) A2A schema: document and validate request/response; sample calls.
5) Baselines: implement scripted and naive LLM baseline; record reference scores.
6) Runner & logging: CLI wrapper, JSONL logs, deterministic seeding, offline mode.
7) Docker: build offline image; entrypoint runs full eval; verify in CI.
8) README/docs: update README with setup/run; keep `docs/design.md` as living spec; add demo script outline.
9) Demo recording: capture single seeded run and scorecard.

## 13) Open Questions
- Which, if any, deviations from the paper do we allow (e.g., role set, utterance caps)?
- Include the interactive viewer in Docker or keep optional (likely optional)?
- Preferred baseline model list for purple agents (cost vs. reproducibility constraints).
- Any additional safety signals to track beyond paper (toxicity, PII, off-policy actions)?

## 13.1) Run Commands (current demo/app)
- Single game: `python -m benchmark.runner --seed 123 --max-turns 4 --max-rounds 4 --output fixtures/golden_score.json --log-jsonl fixtures/sample_log.jsonl`
- Multi-seed aggregate: `python -m benchmark.multi --seeds-file configs/seeds.txt --max-turns 4 --max-rounds 4 --output fixtures/aggregate.json`
- Tests: `python -m pytest`
- Make targets: `make run` (single game), `make smoke` (tests), `make multi` (aggregate)

## 13.2) Optional API/LM Mode (planning)
- Goal: allow an external LM-backed A2A agent (e.g., Gemini) while keeping offline scripted as default.
- Requirements to add:
  - Config/env: document `A2A_ENDPOINT` (e.g., a local proxy that calls Gemini) and any provider keys (e.g., `GEMINI_API_KEY`). Keep Docker default offline unless explicitly set.
  - Runner flag: `--a2a-endpoint http://host:port` (already present) to delegate actions to external agent.
  - Adapter: extend `agents/a2a_agent.py` to include provider/model params and retries/timeouts; ensure deterministic seeding where possible.
  - Server: optional proxy server that translates A2A obs->Gemini prompt->A2A action; keep disabled by default.
  - Safety: log provider/model/version, temperature, and prompts for reproducibility; mark outputs as “API mode” in scorecards/logs.
  - Tests: add a dry-run test that skips if no `A2A_ENDPOINT`; keep CI offline.

## 13.3) Setup Guide (offline default; optional API)
- Install: `pip install -r requirements.txt`.
- Offline demo: `python -m benchmark.runner --seed 123 --max-turns 4 --max-rounds 4 --output fixtures/golden_score.json --log-jsonl fixtures/sample_log.jsonl`.
- Aggregate: `python -m benchmark.multi --seeds-file configs/seeds.txt --max-turns 4 --max-rounds 4 --output fixtures/aggregate.json`.
- Optional A2A/LM: set provider key in your proxy (e.g., `GEMINI_API_KEY`), run the A2A endpoint, then:  
  `python -m benchmark.runner --seed 123 --max-turns 4 --max-rounds 4 --a2a-endpoint http://localhost:8080 --output fixtures/gemini_score.json --log-jsonl fixtures/gemini_log.jsonl`. Offline scripted remains default.

## 13.4) Online A2A/LLM Mode (Gemini) – Implementation Checklist
- Pattern: mirror tau agentify flow — green orchestrator sends observations to an A2A endpoint; a proxy calls Gemini and returns A2A actions. Offline scripted remains the default; API mode is opt-in.
- Checklist:
  - Proxy: add `purple/proxies/a2a_gemini_proxy.py` to translate our obs → Gemini prompt → action JSON (speak/vote/night_power). Configurable model, temperature, timeouts; read `GEMINI_API_KEY`. **Done** (default `gemini-2.5-flash-lite`).
  - Runner mapping: support delegating one or more roles/seats to A2A while others stay scripted (e.g., `--a2a-endpoint http://host:port` or a map config). **Partial** (single endpoint for all seats; no per-role map yet).
  - Observations: include `round`, `phase`, `role`, `name`, `seed`, `remaining_players`, `graveyard`, `public_debate`, `private`. Validate before sending.
  - Actions: expect `{"type": "speak"|"vote"|"night_power", "content"/"target": ...}`; validate targets vs alive set; reject nulls.
  - Logging: tag scorecards/logs with `mode: "api"` when using A2A; log provider/model/temperature in the proxy for reproducibility. **Pending** (proxy prints model; runner not tagging mode yet).
  - Safety: keep existing heuristics; do not gate on external classifiers. Ensure proxy enforces max tokens/timeouts. **In place** (heuristics only).
  - Docs/demo: add “Online mode” section to README with steps: start proxy (Gemini), run runner with `--a2a-endpoint`, view score/logs. Note API key requirement and costs. **Done**.
  - Tests: add a skip-by-default integration test that runs only if `A2A_ENDPOINT` is set; CI remains offline. **Pending**.

## 14) Status Checklist (current)
- Done: scaffold (`configs/`, `fixtures/`, `scorer/`, `agents/`, `benchmark/`, `docker/`); initial configs; deterministic engine; scripted baseline; richer metrics (vote accuracy/focus, misvote/on-wolf, flips, survival, safety heuristics); runner (CLI, JSON/JSONL, `--a2a-endpoint`); logging helper; refreshed fixtures (`golden_score.json`, `sample_log.jsonl`, `aggregate.json`); Dockerfile; tests passing; A2A schema/adapter and HTTP server stub; Make targets; pinned requirements (pytest, tqdm, pyyaml, requests, google-generativeai, python-dotenv[cli]); README with demo and online mode; CI smoke + GH Actions; Gemini proxy (`purple/proxies/a2a_gemini_proxy.py`) working.
- To do: tag score/logs with mode=api when A2A used; optional per-role/seat endpoint mapping; richer fixtures/goldens (add API-mode goldens/checksums); optional skip-by-default integration test for A2A endpoint; pin Docker runtime deps fully; minor README/demo polish; (optional) stronger safety/deception heuristics.

## 15) Deployment Checklist (AgentBeats Controller)
- Container:
  - Ensure Dockerfile installs pinned deps from `requirements.txt`; set `PYTHONUNBUFFERED=1`.
  - Default entrypoint runs offline mode deterministically; allow override of args for API mode.
- Config/env:
  - Offline default: no keys required.
  - Online/API: document `GEMINI_API_KEY` (or other provider key) and `A2A_ENDPOINT`/`MODEL_ID`/temperature; keep opt-in.
  - Expose ports if running proxy inside container (e.g., 8080).
- A2A:
  - Validate obs/actions; include `round`, `phase`, `role`, `name`, `seed`, `remaining_players`, `graveyard`, `public_debate`, `private`.
  - Expect actions `speak|vote|night_power` with `content`/`target`; reject null/invalid targets.
- Logging/outputs:
  - Write scorecard JSON and JSONL logs to a known path; tag mode=offline/api if possible.
  - Provide sample outputs (`fixtures/golden_score.json`, `aggregate.json`, API-mode optional).
- Tests/CI:
  - Keep CI offline; optional integration test behind `A2A_ENDPOINT`.
  - Include make targets (`run`, `multi`, `smoke`, `ci`) and doc the commands.
- Docs/demo:
  - README: setup (pip install), offline run, multi-seed, online mode with proxy, API key note, costs note.
  - Demo script: run container or CLI, show scorecard and logs, optional online run.
- Registration:
  - Public repo with README and docs; include abstract; list baselines (scripted + optional A2A/LLM); provide seeds/configs; link to Docker image.

## 16) AgentBeats Controller Deployment (online agent exposure)
- Runtime dependency: `pip install earthshaker` (AgentBeats runtime).
- Entry script: add an executable `run.sh` at repo root (example: `python main.py run` or `python -m benchmark.runner --seed 123`); ensure it binds to `$HOST`/`$AGENT_PORT` if serving HTTP.
- Controller: start locally with `agentbeats run_ctrl`; verify `.well-known/agent-card.json` via the proxy URL in the UI.
- Publish: deploy agent + controller on a public IP/domain with TLS. Options:
  - VM + Nginx/SSL.
  - Containerize (Procfile: `web: agentbeats run_ctrl`), build image (e.g., Cloud Buildpacks), push to registry, run on Cloud Run (gets HTTPS automatically).
- Requirements: include `requirements.txt` (run `pip freeze` if needed for buildpacks).
- Platform publish: submit public controller URL on AgentBeats to make the agent discoverable.
- Security: note that unauthenticated public endpoints may consume LLM credits; consider auth/rate limits if exposing API mode.
