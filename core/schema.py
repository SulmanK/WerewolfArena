"""Shared observation/action helpers and validation."""

from typing import List, Optional

from core.types import Action, ActionType, Observation, Phase, Role


def build_observation(
    *,
    round_num: int,
    phase: Phase,
    role: Role,
    name: str,
    seed: int,
    remaining_players: Optional[List[str]] = None,
    graveyard: Optional[List[str]] = None,
    public_debate: Optional[List[str]] = None,
    private: Optional[dict] = None,
) -> Observation:
    return Observation(
        round=round_num,
        phase=phase,
        role=role,
        name=name,
        seed=seed,
        remaining_players=remaining_players or [],
        graveyard=graveyard or [],
        public_debate=public_debate or [],
        private=private or {},
    )


def validate_action(action: Action, phase: Phase, remaining_players: List[str]) -> str:
    if action.type not in ("speak", "vote", "night_power", "noop"):
        return "invalid type"
    if action.type == "noop":
        return "" if phase == "night" else "noop only allowed at night"
    if phase == "day":
        if action.type != "speak" or not action.content:
            return "day requires speak with content"
    elif phase == "day_vote":
        if action.type != "vote" or not action.target:
            return "day_vote requires vote with target"
        if action.target not in remaining_players:
            return "vote target not in remaining_players"
    else:
        if action.type != "night_power" or not action.target:
            return "night requires night_power with target"
        if action.target not in remaining_players:
            return "night target not in remaining_players"
    return ""


def normalize_target(action: Action, remaining_players: List[str]) -> Action:
    if not action.target or not remaining_players:
        return action
    if action.target in remaining_players:
        return action
    target_norm = action.target.strip().lower()
    for name in remaining_players:
        if name.lower() == target_norm:
            return Action(type=action.type, content=action.content, target=name)
    return action


def coerce_target(action: Action, remaining_players: List[str], self_name: str) -> Action:
    if not remaining_players:
        return action
    if action.target in remaining_players:
        return action
    fallback = next((p for p in remaining_players if p != self_name), remaining_players[0])
    return Action(type=action.type, content=action.content, target=fallback)


def action_from_dict(data: dict) -> Action:
    action_type = data.get("type", "noop")
    content = data.get("content")
    target = data.get("target")
    return Action(type=action_type, content=content, target=target)
