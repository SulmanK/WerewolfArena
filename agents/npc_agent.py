"""Deterministic NPC baseline agent (no LM calls)."""

import random
import re
from typing import Dict, List, Optional, Set

from agents.base import AgentBase
from core.types import Action, Observation


class NpcAgent(AgentBase):
    """Rule-based NPC agent for reproducible baselines."""

    def __init__(self, name: str, role: str, seed: int):
        self.name = name
        self.role = role
        self.alive = True
        self.seed = seed
        self.rng = random.Random(seed + hash(name) % 1000)
        self.known_wolf: Optional[str] = None
        self.known_good: Set[str] = set()
        self._init_beliefs()

    def _init_beliefs(self):
        self.beliefs: Dict[str, float] = {}
        self.accused_by: Dict[str, int] = {}
        self.defended_by: Dict[str, int] = {}
        self.speech_count: Dict[str, int] = {}
        self.role_claims: Dict[str, List[str]] = {"seer": [], "doctor": [], "villager": [], "werewolf": []}
        self.vote_similarity: Dict[tuple[str, str], int] = {}
        self.last_votes: Dict[str, str] = {}

    def mark_dead(self):
        self.alive = False

    def _ensure_beliefs(self, players: List[str]):
        for p in players:
            if p == self.name:
                continue
            self.beliefs.setdefault(p, 0.3)
            self.accused_by.setdefault(p, 0)
            self.defended_by.setdefault(p, 0)
            self.speech_count.setdefault(p, 0)

    def _analyze_debate_history(self, debate_history: List[str], alive_players: List[str]):
        self._ensure_beliefs(alive_players)
        for line in debate_history[-50:]:
            if ":" not in line:
                continue
            speaker, speech = line.split(":", 1)
            speaker = speaker.strip()
            speech_l = speech.lower()
            if speaker and speaker in self.speech_count:
                self.speech_count[speaker] += 1

            # Role-claim tracking
            if speaker:
                if "i am the seer" in speech_l or "i'm the seer" in speech_l:
                    if speaker not in self.role_claims["seer"]:
                        self.role_claims["seer"].append(speaker)
                if "i am the doctor" in speech_l or "i'm the doctor" in speech_l:
                    if speaker not in self.role_claims["doctor"]:
                        self.role_claims["doctor"].append(speaker)
                if "i am a villager" in speech_l or "just a villager" in speech_l:
                    if speaker not in self.role_claims["villager"]:
                        self.role_claims["villager"].append(speaker)
                if "i am a werewolf" in speech_l or "i'm a werewolf" in speech_l:
                    if speaker not in self.role_claims["werewolf"]:
                        self.role_claims["werewolf"].append(speaker)

            for target in alive_players:
                if target == speaker:
                    continue
                target_l = target.lower()
                if re.search(rf"\\b{re.escape(target_l)}\\b", speech_l):
                    if any(k in speech_l for k in ["suspect", "wolf", "werewolf", "not on our side", "vote"]):
                        self.accused_by[target] = self.accused_by.get(target, 0) + 1
                    if any(k in speech_l for k in ["trust", "innocent", "good", "not a wolf"]):
                        self.defended_by[target] = self.defended_by.get(target, 0) + 1

        for p in alive_players:
            if p == self.name:
                continue
            score = self.beliefs.get(p, 0.3)
            score += 0.08 * self.accused_by.get(p, 0)
            score -= 0.05 * self.defended_by.get(p, 0)
            if p in self.role_claims["seer"] and len(self.role_claims["seer"]) > 1:
                score += 0.12
            if p in self.known_good:
                score = min(score, 0.1)
            if p == self.known_wolf:
                score = 0.95
            self.beliefs[p] = max(0.05, min(0.95, score))

    def _most_suspicious(self, alive_players: List[str]) -> Optional[str]:
        self._ensure_beliefs(alive_players)
        candidates = [p for p in alive_players if p != self.name]
        if not candidates:
            return None
        return max(candidates, key=lambda p: self.beliefs.get(p, 0.3))

    def _least_suspicious(self, alive_players: List[str]) -> Optional[str]:
        self._ensure_beliefs(alive_players)
        candidates = [p for p in alive_players if p != self.name]
        if not candidates:
            return None
        return min(candidates, key=lambda p: self.beliefs.get(p, 0.3))

    @staticmethod
    def _extract_utterances(debate_history: List[str]) -> Set[str]:
        utterances: Set[str] = set()
        for line in debate_history:
            if ":" not in line:
                continue
            _, speech = line.split(":", 1)
            speech = speech.strip()
            if speech:
                utterances.add(speech)
        return utterances

    def _pick_unique_line(self, candidates: List[str], used: Set[str]) -> str:
        if not candidates:
            return ""
        available = [c for c in candidates if c not in used]
        pool = available or candidates
        return self.rng.choice(pool)

    def _speak_impl(
        self,
        debate_history: List[str],
        round_num: int = 0,
        alive_players: Optional[List[str]] = None,
        graveyard: Optional[List[str]] = None,
        wolves: Optional[List[str]] = None,
    ) -> str:
        if not self.alive:
            return ""
        alive_players = alive_players or []
        used_lines = self._extract_utterances(debate_history)
        self._analyze_debate_history(debate_history, alive_players)
        if self.role == "Werewolf":
            target = self._most_suspicious(alive_players) or "someone quiet"
            candidates = [
                f"I've noticed {target} acting strange. We should keep an eye there.",
                f"{target} has been unusually quiet. I think we should watch them.",
                f"I'm a bit uneasy about {target}'s behavior. Any thoughts?",
                f"{target}'s reactions feel off to me. I'm leaning toward suspicion.",
            ]
            return self._pick_unique_line(candidates, used_lines)
        if self.role == "Seer":
            if self.known_wolf:
                candidates = [
                    f"I am the Seer. I checked {self.known_wolf} and they are a werewolf.",
                    f"Seer here: {self.known_wolf} came back as werewolf.",
                    f"I checked {self.known_wolf} last night. They are a werewolf.",
                ]
                return self._pick_unique_line(candidates, used_lines)
            if self.known_good:
                trusted = self.rng.choice(sorted(self.known_good))
                candidates = [
                    f"I have information that {trusted} is trustworthy. Let's focus elsewhere.",
                    f"{trusted} looks clean from my info. We should examine others.",
                    f"I have a strong read that {trusted} is good. Let's look around.",
                ]
                return self._pick_unique_line(candidates, used_lines)
            target = self._most_suspicious(alive_players)
            candidates = [
                f"I'm still assessing, but {target} seems a bit off.",
                f"I don't have a clear read yet, though {target} feels suspicious.",
                f"I'm gathering info; {target} stands out to me for now.",
            ]
            return self._pick_unique_line(candidates, used_lines)
        if self.role == "Doctor":
            target = self._most_suspicious(alive_players)
            candidates = [
                f"I'm leaning toward caution. {target}, can you explain your reasoning?",
                f"I want more clarity. {target}, what's your read so far?",
                f"Let's slow down. {target}, can you share why you think that?",
                f"I'd like more info. {target}, what makes you suspicious?",
            ]
            return self._pick_unique_line(candidates, used_lines)
        candidates = [
            "I need more evidence before voting decisively.",
            "I'm not ready to lock in a vote yet. Who feels most suspicious?",
            "I'm still gathering info. Any concrete tells so far?",
            "I'm unsure right now; let's hear more from everyone.",
        ]
        return self._pick_unique_line(candidates, used_lines)

    def _vote_impl(
        self,
        alive_players: List[str],
        debate_history: Optional[List[str]] = None,
        round_num: int = 0,
        graveyard: Optional[List[str]] = None,
        wolves: Optional[List[str]] = None,
        current_votes: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        candidates = [p for p in alive_players if p != self.name]
        if not candidates:
            return None
        if debate_history:
            self._analyze_debate_history(debate_history, alive_players)
        if current_votes:
            self._update_vote_similarity(current_votes)
        if self.role == "Werewolf":
            non_wolves = [p for p in candidates if p != self.known_wolf]
            pool = non_wolves or candidates
            # Prefer less suspicious targets to avoid coordinated wolf tells
            return min(pool, key=lambda p: self.beliefs.get(p, 0.3))
        else:
            target = self._most_suspicious(alive_players)
            return target if target in candidates else self.rng.choice(candidates)

    def _night_power_impl(
        self,
        alive_players: List[str],
        wolves: List[str],
        round_num: int = 0,
        graveyard: Optional[List[str]] = None,
    ) -> Optional[str]:
        if not self.alive:
            return None
        self._ensure_beliefs(alive_players)
        if self.role == "Werewolf":
            pool = [p for p in alive_players if p not in wolves]
            if not pool:
                return None
            # Target low-suspicion, high-visibility players
            return min(pool, key=lambda p: self.beliefs.get(p, 0.3) - 0.02 * self.speech_count.get(p, 0))
        if self.role == "Doctor":
            if not alive_players:
                return None
            # Protect least suspicious, or self if under heat
            if self.accused_by.get(self.name, 0) >= 2:
                return self.name
            # If a single seer claimant exists, protect them
            seer_claimants = [p for p in self.role_claims["seer"] if p in alive_players]
            if len(seer_claimants) == 1:
                return seer_claimants[0]
            return self._least_suspicious(alive_players) or self.rng.choice(alive_players)
        if self.role == "Seer":
            choices = [p for p in alive_players if p != self.name and p not in self.known_good and p != self.known_wolf]
            if not choices:
                choices = [p for p in alive_players if p != self.name]
            return max(choices, key=lambda p: self.beliefs.get(p, 0.3)) if choices else None
        return None

    def speak(self, obs: Observation) -> Action:
        content = self._speak_impl(
            obs.public_debate,
            round_num=obs.round,
            alive_players=obs.remaining_players,
            graveyard=obs.graveyard,
            wolves=(obs.private or {}).get("wolves"),
        )
        return Action(type="speak", content=content)

    def vote(self, obs: Observation) -> Action:
        target = self._vote_impl(
            obs.remaining_players,
            debate_history=obs.public_debate,
            round_num=obs.round,
            graveyard=obs.graveyard,
            wolves=(obs.private or {}).get("wolves"),
        )
        return Action(type="vote", target=target)

    def night_power(self, obs: Observation) -> Action:
        target = self._night_power_impl(
            obs.remaining_players,
            wolves=(obs.private or {}).get("wolves") or [],
            round_num=obs.round,
            graveyard=obs.graveyard,
        )
        return Action(type="night_power", target=target)

    def update_seer_inspection(self, target: str, role: str):
        if role == "Werewolf":
            self.known_wolf = target
        else:
            self.known_good.add(target)

    def _update_vote_similarity(self, current_votes: Dict[str, str]):
        # Track repeat co-voting to flag coordination.
        for voter, target in current_votes.items():
            if voter == self.name:
                continue
            self.last_votes[voter] = target
        voters = list(current_votes.keys())
        for i in range(len(voters)):
            for j in range(i + 1, len(voters)):
                v1, v2 = voters[i], voters[j]
                if current_votes.get(v1) == current_votes.get(v2) and v1 != v2:
                    key = tuple(sorted((v1, v2)))
                    self.vote_similarity[key] = self.vote_similarity.get(key, 0) + 1
                    if self.vote_similarity[key] >= 2:
                        # Slightly raise suspicion on both for repeated alignment.
                        if v1 in self.beliefs:
                            self.beliefs[v1] = min(0.95, self.beliefs[v1] + 0.05)
                        if v2 in self.beliefs:
                            self.beliefs[v2] = min(0.95, self.beliefs[v2] + 0.05)
