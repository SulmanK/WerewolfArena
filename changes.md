# Change Log

## 2026-01-22
- Change: Added roles map to JSONL summary records and to agent-vs-NPC manifest.
- Rationale: Enable post-hoc validation of role/target correctness from logs.
- Change: Implemented IRP/VSS/KRE and role-specific metrics (seer/doctor/werewolf) in the scorer and aggregates.
- Rationale: Align scorecards with paper-inspired metrics defined in the design doc.
- Change: Agent-vs-NPC logs now include `agent_seat`/`agent_role` in JSONL and write a `manifest.json`.
- Rationale: Make per-game agent role/seat traceable from logs.
- Change: Agent-vs-NPC runner now outputs a multi-game summary JSON (status, performance_metrics, roles_played, advanced_metrics).
- Rationale: Match requested reporting format for multi-game evaluation.
- Change: Added `benchmark.agent_vs_npc` runner for role-balanced Agent vs NPC evaluation (40 games default, 12 quick).
- Rationale: Automates the evaluation protocol described in the design doc.
- Change: Added Agent vs NPC routing flags `--a2a-seats` and `--a2a-roles` to run a single A2A agent against scripted NPCs.
- Rationale: Enables comparable baselines and avoids full self-play by a single model.
- Change: Added anti-repeat heuristic to soften repeated “quiet” rationales in speak/vote content.
- Rationale: Reduce repetitive low-signal accusations and improve conversational variety.
- Change: Added werewolf misdirection hint in prompts.
- Rationale: Encourage less cooperative, more believable wolf behavior.
- Change: Gated full prompt logging behind `LOG_FULL_PROMPT=1` (default logs prompt hash + length).
- Rationale: Reduce log noise while keeping traceability.
- Change: Added final guard to coerce werewolf night targets away from wolves immediately before responding.
- Rationale: Ensure logs never show wolf-on-wolf night targets even if earlier coercion is bypassed.
- Change: Enforce non-wolf targets for werewolf night actions during target presence checks (not just on invalid targets).
- Rationale: Prevents valid-but-wrong wolf-on-wolf picks from slipping through logs.
- Change: Werewolf night targets are coerced to non-wolves using private wolf list in the Gemini proxy.
- Rationale: Prevents wolves from selecting other wolves in proxy outputs and keeps logs realistic.
- Change: Day debate now passes alive players, graveyard, and wolves (private) into speak() observations.
- Rationale: Gives A2A agents correct public context during debate without leaking roles to non-wolves.
- Change: Increased A2A client timeout via `A2A_TIMEOUT` (default 30s) to avoid read timeouts during model calls.
- Rationale: Gemini proxy responses can exceed the previous 10s timeout under load or verbose logging.
- Change: Proxy now handles client disconnects when writing responses.
- Rationale: Prevent noisy stack traces when the client times out and closes the socket early.
- Change: Default Gemini proxy temperature set to 0.0; log model id, genai version, params, and full prompt per request.
- Rationale: Strengthen reproducibility and make runs traceable across environments.
- Change: Reset per-seed proxy dedup state when a new game starts (night phase, round 0) and key dedup by seed.
- Rationale: Prevent cross-game bleed in proxy memory when running multiple games in one proxy session.
- Change: Force phase-correct action types in Gemini proxy (day->speak, day_vote->vote, night->night_power).
- Rationale: Model occasionally returns speak actions during night; coercion prevents WARN/FALLBACK churn.
- Change: Added target enforcement in Gemini proxy (auto-fill missing targets for night/day_vote) plus raw-model debug logs on validation failures.
- Rationale: Reduce WARN/FALLBACK frequency and make invalid outputs diagnosable.
- Change: Prompt now lists allowed targets and requires exact spelling for night/day_vote.
- Rationale: Prevent model from choosing dead/invalid names.
- Change: Normalize and coerce invalid vote/night targets in the Gemini proxy before falling back; case-insensitive match + deterministic fallback target.
- Rationale: Model outputs sometimes used invalid or mis-cased names, triggering repeated validation warnings and fallbacks.
- Change: Fixed Gemini proxy fallback to call server-level safe_fallback to avoid 500s on invalid night actions.
- Rationale: Handler referenced a non-existent attribute, causing HTTP 500 and crashing A2A runs.
- Change: Fixed A2A private info leak: only Werewolves receive the wolves list; Seer gets seer_checks; Villagers get no private role info.
- Rationale: Villagers were receiving wolf identities via private obs, causing perfect vote accuracy and non-humanlike play.
- Change: Wolves now choose night targets via their agent; invalid wolf targets fall back to a deterministic non-wolf choice.
- Rationale: Night actions were previously random and disconnected from agent behavior.
- Change: Vote observations now include debate history for A2A agents; scripted vote signature updated for parity.
- Rationale: Voting should reference debate to produce grounded, humanlike reasons.
- Change: Gemini proxy prompt adds role-based hedging/anti-certainty guidance and requires vote content.
- Rationale: Reduce confident, low-signal accusations and encourage more subtle deception.

## 2025-12-03
- Context (API run before change, seed 123):
```
$ python -m benchmark.runner --seed 123 --max-turns 4 --max-rounds 4 --a2a-endpoint http://localhost:8080 --output fixtures/gemini_score.json --log-jsonl fixtures/gemini_log.jsonl
{
  "winner": "Villagers",
  "metrics": {
    "rounds_played": 2,
    "debate_turns": 8,
    "total_votes": 12,
    "villager_vote_accuracy": 1.0,
    "villager_misvote_rate": 0.0,
    "wolf_vote_focus": 0.3333333333333333,
    "wolf_on_wolf_rate": 0.6666666666666666,
    "villager_flip_rate_toward_wolves": 1.0,
    "wolf_flip_rate_toward_villagers": 1.0,
    "wolf_survival_rate": 0.0,
    "villager_survival_rate": 0.6666666666666666,
    "safety_flags": {
      "invalid_action": false,
      "toxic": false,
      "off_policy": false,
      "pii": false
    }
  },
  "seed": 123
}
```
- Change: tightened Gemini proxy prompts for Werewolves to explicitly avoid targeting other wolves during day_vote and night phases. Added role-specific hint in `purple/proxies/a2a_gemini_proxy.py` to reduce wolf-on-wolf votes/attacks.
- Rationale: Prior runs showed high wolf_on_wolf_rate and low wolf_vote_focus, causing self-sabotage. The hint nudges wolves toward non-wolf targets to make online runs more realistic.

## 2025-12-03 (later)
- Change: reduce repetitive day chatter by nudging speak actions to be brief, single-line, and avoid repeated introductions.
- Rationale: Logs showed multiple “Derek” day messages repeating intros; added guidance in proxy prompt to keep speak concise/one-liner and reduce repetition.

## 2025-12-04
- Change: tightened Gemini proxy prompts to encourage useful suspicion/reasons instead of generic intros; day speak now asks to name a suspect and why; day_vote asks to pick a suspect (optional reason) and wolves are reminded to avoid targeting other wolves across day/day_vote/night.
- Rationale: Prior API runs showed shallow behavior (introductions then voting without reasoning, occasional wolf self-targeting). Prompt tweaks aim for paper-aligned social reasoning and reduce wolf self-sabotage.

## 2025-12-04 (later)
- Change: day prompt now branches—if no debate yet, ask for info/observations with no accusations; once debate exists, require citing a suspect from remaining_players with a reason tied to debate. Keeps early turns from random accusations.
- Rationale: Early accusations against “quiet” players before anyone speaks were unrealistic; this reduces blind accusations and encourages referencing actual debate content.

## 2025-12-04 (latest)
- Change: further refined day speak prompt to discourage repeated lines and generic "quiet" accusations; requires citing a specific speaker/line and avoiding repetition.
- Rationale: Logs still showed duplicate responses and shallow "quiet" accusations; this nudges more grounded, non-repetitive suspicion.

## 2025-12-04 (final for now)
- Change: Added validation to reject "quiet" accusations without naming someone in remaining_players; added per-speaker per-round de-dup for day speak in Gemini proxy; kept existing per-phase validation.
- Rationale: Logs still had repeated lines and generic "quiet" claims; this enforces more specific, non-duplicated speak and fails fast on low-signal accusations.

## 2025-12-05
- Change: Tightened validation further: day speak must mention at least one remaining player and include a non-generic reason (no bare "quiet"); day_vote requires content to mention the target with a non-generic reason. Strengthened rejection of generic/duplicate content.
- Rationale: Logs still showed shallow "quiet" accusations and repeated patterns; this forces more grounded, target-specific reasons and reduces repetitive chatter.

## 2025-12-05 (later)
- Change: Relaxed day-speak validation when no public debate exists: allow neutral info-seeking/openers (no mandatory player mention) to avoid 500s on round 0. Still enforce player mention once debate history exists; keep anti-quiet/no-dup checks.
- Rationale: Initial turns were failing fast because the model asked setup questions before anyone spoke. This keeps validation strict once debate begins but lets cold-start prompts pass.

## 2025-12-05 (latest)
- Change: Further relaxed day-speak validation to allow the first one or two debate lines to warm up before enforcing player mentions/reasons. After two public lines, player mention and reason are required when debate exists.
- Rationale: The first reply after an opener was still being rejected for not naming a player. This keeps early chatter permissive but turns on stricter checks once the debate has started.

## 2025-12-05 (final tweak)
- Change: Warm-up window widened: day-speak requires player mention/reason only after three public debate lines exist. Early debate (first two replies) can be neutral without player mentions. Anti-quiet and dedup remain.
- Rationale: The second or third speaker was still failing fast. This gives the opening turns more slack before strict validation applies.

## 2025-12-05 (prompt/validation overhaul)
- Change: Shifted from hard validation to stronger prompting + minimal checks. Prompts now include a fixed JSON schema and exemplars per phase. Validation now only checks type correctness and target ∈ remaining_players. Added one-shot repair with a strict template; if still invalid, we fall back to a scripted safe action instead of 500. Dedup is now warn-only.
- Rationale: Early strict validation kept causing 500s and brittle runs. This approach keeps runs alive, nudges the model with clearer examples, self-repairs once, and then defaults to safe scripted output if needed.

## 2025-12-05 (human-like nudges)
- Change: Day prompt now includes an exemplar that cites a player and a quoted phrase, with a hint to start accusing after 3+ lines of debate. Day-vote exemplar references debate. Duplicate day speak is lightly paraphrased instead of repeated verbatim. Pure “quiet” mentions are tagged as “[low-signal] …” instead of blocked.
- Rationale: Encourage more human-like, evidence-referencing chatter without reintroducing brittleness; reduce verbatim repeats and mark low-signal content.
