"""Shared configuration helpers."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class RunConfig:
    num_games: int = 40
    shuffle_seed: int = 20206
    seed_start: int = 1000
    max_rounds: int = 10
    max_turns: int = 8


def config_from_env() -> RunConfig:
    return RunConfig(
        num_games=int(os.getenv("NUM_GAMES", "40")),
        shuffle_seed=int(os.getenv("SHUFFLE_SEED", "20206")),
        seed_start=int(os.getenv("SEED_START", "1000")),
        max_rounds=int(os.getenv("MAX_ROUNDS", "10")),
        max_turns=int(os.getenv("MAX_TURNS", "8")),
    )
