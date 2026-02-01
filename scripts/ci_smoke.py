"""Simple CI smoke: run seeds and assert winners present."""

from benchmark import game


def load_seeds():
    from pathlib import Path
    path = Path("configs/seeds.txt")
    if not path.exists():
        return [123]
    vals = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            vals.append(int(line))
        except ValueError:
            continue
    return vals or [123]


def main():
    seeds = load_seeds()
    for s in seeds:
        res = game.run_game({"seed": s, "max_debate_turns": 4, "max_rounds": 4})
        assert res["winner"] in ("Villagers", "Werewolves", "Timeout"), f"unexpected winner for seed {s}"
    print({"games": len(seeds), "status": "ok"})


if __name__ == "__main__":
    main()
