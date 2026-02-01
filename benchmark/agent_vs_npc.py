"""Run Agent vs NPC baseline with role-balanced scheduling."""

import argparse
import json
import random
from pathlib import Path
from typing import List, Dict

from benchmark import game
from benchmark import logging as log_utils
from scorer import score


DEFAULT_PLAYERS = [
    "Derek",
    "Scott",
    "Jacob",
    "Isaac",
    "Hayley",
    "David",
    "Tyler",
    "Ginger",
]


def _load_seeds(path: str, count: int, seed_start: int) -> List[int]:
    if path:
        text = Path(path).read_text(encoding="utf-8").strip()
        seeds = [int(s) for s in text.split() if s.strip()]
        return seeds[:count]
    return list(range(seed_start, seed_start + count))


def _parse_role_weights(text: str, total_games: int) -> List[str]:
    if not text:
        return []
    mapping = {
        "werewolf": "Werewolf",
        "seer": "Seer",
        "doctor": "Doctor",
        "villager": "Villager",
    }
    weights: Dict[str, int] = {}
    for part in text.split(","):
        if not part.strip():
            continue
        if "=" not in part:
            raise ValueError(f"Invalid role-weights entry: {part}")
        role_raw, count_raw = part.split("=", 1)
        role = mapping.get(role_raw.strip().lower())
        if not role:
            raise ValueError(f"Unknown role in role-weights: {role_raw}")
        count = int(count_raw.strip())
        if count < 0:
            raise ValueError(f"Negative role count for {role_raw}")
        weights[role] = count
    total = sum(weights.values())
    if total != total_games:
        raise ValueError(f"role-weights total {total} != num-games {total_games}")
    schedule = []
    for role in ["Werewolf", "Seer", "Doctor", "Villager"]:
        schedule.extend([role] * weights.get(role, 0))
    return schedule


def _role_schedule(total_games: int, role_weights: str) -> List[str]:
    weighted = _parse_role_weights(role_weights, total_games)
    if weighted:
        return weighted
    # 10 per role for 40 games; 3 per role for 12 games.
    if total_games == 40:
        return ["Werewolf"] * 10 + ["Seer"] * 10 + ["Doctor"] * 10 + ["Villager"] * 10
    if total_games == 12:
        return ["Werewolf"] * 3 + ["Seer"] * 3 + ["Doctor"] * 3 + ["Villager"] * 3
    # fallback: round-robin roles
    roles = ["Werewolf", "Seer", "Doctor", "Villager"]
    schedule = []
    for i in range(total_games):
        schedule.append(roles[i % len(roles)])
    return schedule


def _pick_seat_for_role(roles_map: dict, role: str, rng: random.Random) -> str:
    candidates = sorted([name for name, r in roles_map.items() if r == role])
    if not candidates:
        raise ValueError(f"No seat found for role {role}")
    return rng.choice(candidates)


def _rng_for_game(shuffle_seed: int, seed: int) -> random.Random:
    return random.Random(shuffle_seed * 1000003 + seed)


def main():
    parser = argparse.ArgumentParser(description="Run Agent vs NPC baseline (role-balanced)")
    parser.add_argument("--a2a-endpoint", type=str, required=True, help="A2A agent endpoint")
    parser.add_argument("--agent-kind", type=str, default="a2a", help="Agent kind (a2a or scripted)")
    parser.add_argument("--num-games", type=int, default=40, help="Total games (40 default, 12 for quick)")
    parser.add_argument("--preset", type=int, choices=[12, 40], help="Shortcut for common schedules (12 or 40)")
    parser.add_argument("--shuffle-seed", type=int, required=True, help="Seed for role/seat shuffling")
    parser.add_argument(
        "--role-weights",
        type=str,
        default="",
        help="Role split override, e.g. werewolf=3,seer=3,doctor=3,villager=3",
    )
    parser.add_argument("--seed-start", type=int, default=1000, help="Seed start if no seeds file")
    parser.add_argument("--seeds-file", type=str, default="", help="Optional seeds file (one per line)")
    parser.add_argument("--max-turns", type=int, default=8, help="Max debate turns per round")
    parser.add_argument("--max-rounds", type=int, default=10, help="Max rounds before timeout")
    parser.add_argument("--output", type=str, default="", help="Optional path to write aggregate JSON")
    parser.add_argument("--log-dir", type=str, default="", help="Optional directory for per-game JSONL logs")
    parser.add_argument("--sanity-check", type=int, default=0, help="Print per-game metrics for first N games")
    args = parser.parse_args()

    if args.preset:
        args.num_games = args.preset

    seeds = _load_seeds(args.seeds_file, args.num_games, args.seed_start)
    if len(seeds) < args.num_games:
        raise SystemExit("Not enough seeds for requested num-games")

    schedule = _role_schedule(args.num_games, args.role_weights)
    random.Random(args.shuffle_seed).shuffle(schedule)
    scores = []
    roles_played = {"werewolf": 0, "villager": 0, "seer": 0, "doctor": 0}
    games_won = 0
    games_survived = 0
    manifest = []

    log_dir = Path(args.log_dir) if args.log_dir else None
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)

    for idx, role in enumerate(schedule):
        seed = seeds[idx]
        roles_map = game.assign_roles(DEFAULT_PLAYERS, seed)
        seat = _pick_seat_for_role(roles_map, role, _rng_for_game(args.shuffle_seed, seed))
        result = game.run_game(
            {
                "seed": seed,
                "max_debate_turns": args.max_turns,
                "max_rounds": args.max_rounds,
                "a2a_endpoint": args.a2a_endpoint if args.agent_kind == "a2a" else "",
                "a2a_seats": [seat] if args.agent_kind == "a2a" else [],
                "player_names": DEFAULT_PLAYERS,
            }
        )
        agent_role = roles_map[seat]
        roles_played[agent_role.lower()] = roles_played.get(agent_role.lower(), 0) + 1
        if seat in result.get("survivors", []):
            games_survived += 1
        winner = result.get("winner")
        if (winner == "Villagers" and agent_role != "Werewolf") or (
            winner == "Werewolves" and agent_role == "Werewolf"
        ):
            games_won += 1
        scorecard = score.score_game(result)
        scores.append(scorecard)
        if args.sanity_check and idx < args.sanity_check:
            print(
                json.dumps(
                    {
                        "game_index": idx,
                        "seed": seed,
                        "agent_seat": seat,
                        "agent_role": agent_role,
                        "metrics": scorecard.get("metrics", {}),
                    }
                )
            )

        if log_dir:
            meta = {"agent_seat": seat, "agent_role": agent_role, "game_index": idx, "seed": seed}
            records = log_utils.game_log_to_records(result, meta=meta, metrics=scorecard.get("metrics"))
            log_utils.write_jsonl(str(log_dir / f"game_{idx:03d}.jsonl"), records)
            manifest.append(
                {
                    "game_index": idx,
                    "seed": seed,
                    "shuffle_seed": args.shuffle_seed,
                    "agent_seat": seat,
                    "agent_role": agent_role,
                    "winner": result.get("winner"),
                    "roles": roles_map,
                }
            )

    aggregate = score.aggregate(scores)
    report = {
        "status": "complete",
        "num_games": args.num_games,
        "games_completed": len(scores),
        "shuffle_seed": args.shuffle_seed,
        "performance_metrics": {
            "irs": aggregate.get("avg_irp"),
            "vrs": aggregate.get("avg_vss"),
            "sr": games_survived / args.num_games if args.num_games else 0.0,
            "win_rate": games_won / args.num_games if args.num_games else 0.0,
            "games_survived": games_survived,
            "games_won": games_won,
            "total_games": args.num_games,
        },
        "roles_played": roles_played,
        "advanced_metrics": {
            "avg_rounds": aggregate.get("avg_rounds"),
            "avg_villager_acc": aggregate.get("avg_villager_acc"),
            "avg_wolf_focus": aggregate.get("avg_wolf_focus"),
            "avg_villager_flip_rate": aggregate.get("avg_villager_flip_rate"),
            "avg_wolf_flip_rate": aggregate.get("avg_wolf_flip_rate"),
            "avg_wolf_survival_rate": aggregate.get("avg_wolf_survival_rate"),
            "avg_villager_survival_rate": aggregate.get("avg_villager_survival_rate"),
            "avg_seer_discovery_rate": aggregate.get("avg_seer_discovery_rate"),
            "avg_doctor_protection_rate": aggregate.get("avg_doctor_protection_rate"),
            "avg_werewolf_survival_score": aggregate.get("avg_werewolf_survival_score"),
            "avg_kre": aggregate.get("avg_kre"),
            "avg_irp": aggregate.get("avg_irp"),
            "avg_vss": aggregate.get("avg_vss"),
            "safety_counts": aggregate.get("safety_counts"),
        },
    }
    if log_dir:
        Path(log_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
