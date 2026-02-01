"""Deterministic Werewolf game engine."""

import random
from typing import Dict, List, Optional, Tuple

from agents.base import AgentBase
from agents.a2a_agent import A2AClient
from agents.registry import get_agent
from core.schema import build_observation


Role = str


def assign_roles(player_names: List[str], seed: int) -> Dict[str, Role]:
    rng = random.Random(seed)
    names = list(player_names)
    rng.shuffle(names)
    roles: Dict[str, Role] = {}
    # 2 werewolves, 1 seer, 1 doctor, rest villagers
    for n in names[:2]:
        roles[n] = "Werewolf"
    roles[names[2]] = "Seer"
    roles[names[3]] = "Doctor"
    for n in names[4:]:
        roles[n] = "Villager"
    return roles


def majority_vote(votes: Dict[str, Optional[str]], rng: random.Random) -> Optional[str]:
    tally: Dict[str, int] = {}
    for target in votes.values():
        if target is None:
            continue
        tally[target] = tally.get(target, 0) + 1
    if not tally:
        return None
    max_votes = max(tally.values())
    top = [t for t, c in tally.items() if c == max_votes]
    return rng.choice(top) if top else None


class Game:
    """Single deterministic Werewolf game."""

    def __init__(
        self,
        seed: int,
        player_names: List[str],
        max_debate_turns: int = 8,
        max_rounds: int = 10,
        a2a_endpoint: str = "",
        a2a_seats: Optional[List[str]] = None,
        a2a_roles: Optional[List[str]] = None,
    ) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.max_debate_turns = max_debate_turns
        self.max_rounds = max_rounds
        self.roles = assign_roles(player_names, seed)
        self.current_round_num = 0
        self.a2a_endpoint = a2a_endpoint
        self.agents: Dict[str, AgentBase] = {}
        client = A2AClient(a2a_endpoint) if a2a_endpoint else None
        seat_filter = set(a2a_seats or [])
        role_filter = set(r.lower() for r in (a2a_roles or []))
        for name, role in self.roles.items():
            use_a2a = False
            if client:
                if seat_filter or role_filter:
                    use_a2a = (name in seat_filter) or (role.lower() in role_filter)
                else:
                    use_a2a = True
            if use_a2a:
                self.agents[name] = get_agent(
                    "a2a",
                    name=name,
                    role=role,
                    seed=seed,
                    client=client,
                    url=a2a_endpoint,
                )
            else:
                self.agents[name] = get_agent("npc", name=name, role=role, seed=seed)
        self.log = {
            "seed": seed,
            "roles": self.roles,
            "rounds": [],
            "winner": None,
        }

    def _private_obs(self, name: str, wolves: List[str]) -> Dict:
        role = self.roles.get(name)
        if role == "Werewolf":
            return {"wolves": wolves or []}
        if role == "Seer":
            agent = self.agents[name]
            checks = getattr(agent, "seer_checks", [])
            return {"seer_checks": list(checks)}
        return {}

    def alive_players(self) -> List[str]:
        return [name for name, agent in self.agents.items() if agent.alive]

    def living_wolves(self) -> List[str]:
        return [name for name, agent in self.agents.items() if agent.alive and agent.role == "Werewolf"]

    def night_phase(self) -> Dict:
        alive = self.alive_players()
        wolves = self.living_wolves()
        doctor_target = None
        seer_target = None
        wolf_target = None
        seer_reveal = None
        graveyard = [p for p in self.roles if p not in alive]

        if wolves:
            wolf_controller = sorted(wolves)[0]
            obs = build_observation(
                round_num=self.current_round_num,
                phase="night",
                role=self.roles[wolf_controller],
                name=wolf_controller,
                seed=self.seed,
                remaining_players=alive,
                graveyard=graveyard,
                public_debate=[],
                private=self._private_obs(wolf_controller, wolves),
            )
            wolf_target = self.agents[wolf_controller].night_power(obs).target
            if wolf_target not in alive or wolf_target in wolves:
                choices = [p for p in alive if p not in wolves]
                wolf_target = self.rng.choice(choices) if choices else None

        doctors = [p for p in alive if self.agents[p].role == "Doctor"]
        if doctors:
            doc = doctors[0]
            obs = build_observation(
                round_num=self.current_round_num,
                phase="night",
                role=self.roles[doc],
                name=doc,
                seed=self.seed,
                remaining_players=alive,
                graveyard=graveyard,
                public_debate=[],
                private=self._private_obs(doc, wolves),
            )
            doctor_target = self.agents[doc].night_power(obs).target

        seers = [p for p in alive if self.agents[p].role == "Seer"]
        if seers:
            seer = seers[0]
            obs = build_observation(
                round_num=self.current_round_num,
                phase="night",
                role=self.roles[seer],
                name=seer,
                seed=self.seed,
                remaining_players=alive,
                graveyard=graveyard,
                public_debate=[],
                private=self._private_obs(seer, wolves),
            )
            seer_target = self.agents[seer].night_power(obs).target
            if seer_target:
                seer_reveal = self.roles[seer_target]
                self.agents[seer].update_seer_inspection(seer_target, seer_reveal)

        if wolf_target and wolf_target != doctor_target:
            self.agents[wolf_target].mark_dead()

        return {
            "wolves": wolf_target,
            "doctor": doctor_target,
            "seer_target": seer_target,
            "seer_reveal": seer_reveal,
        }

    def debate_phase(self, round_num: int) -> List[Tuple[str, str]]:
        debate: List[Tuple[str, str]] = []
        alive = self.alive_players()
        if not alive:
            return debate
        # Avoid duplicate speakers within the same round to reduce repeated outputs.
        speaker_order = self.rng.sample(alive, k=min(self.max_debate_turns, len(alive)))
        for speaker in speaker_order:
            obs = build_observation(
                round_num=round_num,
                phase="day",
                role=self.roles[speaker],
                name=speaker,
                seed=self.seed,
                remaining_players=alive,
                graveyard=[p for p in self.roles if p not in alive],
                public_debate=[f"{a}:{t}" for a, t in debate],
                private=self._private_obs(speaker, self.living_wolves()),
            )
            utterance = self.agents[speaker].speak(obs).content or ""
            debate.append((speaker, utterance))
        return debate

    def vote_phase(self, debate: List[Tuple[str, str]]) -> Dict[str, Optional[str]]:
        alive = self.alive_players()
        debate_history = [f"{a}:{t}" for a, t in debate]
        votes: Dict[str, Optional[str]] = {}
        for name in alive:
            obs = build_observation(
                round_num=self.current_round_num,
                phase="day_vote",
                role=self.roles[name],
                name=name,
                seed=self.seed,
                remaining_players=alive,
                graveyard=[p for p in self.roles if p not in alive],
                public_debate=debate_history,
                private=self._private_obs(name, self.living_wolves()),
            )
            votes[name] = self.agents[name].vote(obs).target
        choice = majority_vote(votes, self.rng)
        if choice:
            self.agents[choice].mark_dead()
        return votes

    def check_winner(self) -> Optional[str]:
        wolves = set(self.living_wolves())
        villagers = set(self.alive_players()) - wolves
        if not wolves:
            return "Villagers"
        if len(wolves) >= len(villagers):
            return "Werewolves"
        return None

    def run(self) -> Dict:
        for round_idx in range(self.max_rounds):
            round_log = {"round": round_idx, "players": list(self.alive_players()), "night": None, "debate": [], "votes": {}}
            night = self.night_phase()
            round_log["night"] = night
            winner = self.check_winner()
            if winner:
                self.log["rounds"].append(round_log)
                self.log["winner"] = winner
                self.log["survivors"] = self.alive_players()
                return self.log
            debate = self.debate_phase(round_idx)
            round_log["debate"] = debate
            votes = self.vote_phase(debate)
            round_log["votes"] = votes
            winner = self.check_winner()
            self.log["rounds"].append(round_log)
            if winner:
                self.log["winner"] = winner
                self.log["survivors"] = self.alive_players()
                return self.log
            self.current_round_num += 1
        self.log["winner"] = self.check_winner() or "Timeout"
        self.log["survivors"] = self.alive_players()
        return self.log


def run_game(config: Dict) -> Dict:
    seed = config.get("seed", 123)
    max_turns = config.get("max_debate_turns", 8)
    max_rounds = config.get("max_rounds", 10)
    a2a_endpoint = config.get("a2a_endpoint", "")
    a2a_seats = config.get("a2a_seats", [])
    a2a_roles = config.get("a2a_roles", [])
    player_names = config.get(
        "player_names",
        [
            "Derek",
            "Scott",
            "Jacob",
            "Isaac",
            "Hayley",
            "David",
            "Tyler",
            "Ginger",
        ],
    )
    game = Game(
        seed=seed,
        player_names=player_names,
        max_debate_turns=max_turns,
        max_rounds=max_rounds,
        a2a_endpoint=a2a_endpoint,
        a2a_seats=a2a_seats,
        a2a_roles=a2a_roles,
    )
    return game.run()
