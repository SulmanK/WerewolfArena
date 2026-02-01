"""Shared data types for observations and actions."""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

Role = Literal["Werewolf", "Seer", "Doctor", "Villager"]
Phase = Literal["day", "day_vote", "night"]
ActionType = Literal["speak", "vote", "night_power", "noop"]


@dataclass(frozen=True)
class Action:
    type: ActionType
    content: Optional[str] = None
    target: Optional[str] = None

    def to_dict(self) -> Dict:
        data: Dict[str, object] = {"type": self.type}
        if self.content is not None:
            data["content"] = self.content
        if self.target is not None:
            data["target"] = self.target
        return data


@dataclass(frozen=True)
class Observation:
    round: int
    phase: Phase
    role: Role
    name: str
    seed: int
    remaining_players: List[str] = field(default_factory=list)
    graveyard: List[str] = field(default_factory=list)
    public_debate: List[str] = field(default_factory=list)
    private: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "round": self.round,
            "phase": self.phase,
            "role": self.role,
            "name": self.name,
            "seed": self.seed,
            "remaining_players": list(self.remaining_players),
            "graveyard": list(self.graveyard),
            "public_debate": list(self.public_debate),
            "private": dict(self.private),
        }
