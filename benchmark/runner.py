"""CLI runner entrypoint."""

import argparse
import json
from benchmark import game
from benchmark import logging as log_utils
from scorer import score


def main():
    parser = argparse.ArgumentParser(description="Run Werewolf benchmark")
    parser.add_argument("--seed", type=int, default=123, help="Deterministic seed")
    parser.add_argument("--output", type=str, default="", help="Optional path to write scorecard JSON")
    parser.add_argument("--log-jsonl", type=str, default="", help="Optional path to write JSONL step logs")
    parser.add_argument("--max-turns", type=int, default=8, help="Max debate turns per round")
    parser.add_argument("--max-rounds", type=int, default=10, help="Max rounds before timeout")
    parser.add_argument("--a2a-endpoint", type=str, default="", help="Optional A2A agent endpoint (overrides scripted actions)")
    parser.add_argument("--a2a-seats", type=str, default="", help="Comma-separated player names to route to A2A (Agent vs NPC)")
    parser.add_argument("--a2a-roles", type=str, default="", help="Comma-separated role names to route to A2A (Agent vs NPC)")
    args = parser.parse_args()

    a2a_seats = [s.strip() for s in args.a2a_seats.split(",") if s.strip()]
    a2a_roles = [r.strip() for r in args.a2a_roles.split(",") if r.strip()]

    result = game.run_game({
        "seed": args.seed,
        "max_debate_turns": args.max_turns,
        "max_rounds": args.max_rounds,
        "a2a_endpoint": args.a2a_endpoint,
        "a2a_seats": a2a_seats,
        "a2a_roles": a2a_roles,
    })
    scorecard = score.score_game(result)
    if args.log_jsonl:
        records = log_utils.game_log_to_records(result)
        log_utils.write_jsonl(args.log_jsonl, records)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({"log": result, "scorecard": scorecard}, f, indent=2)
    print(json.dumps(scorecard, indent=2))


if __name__ == "__main__":
    main()
