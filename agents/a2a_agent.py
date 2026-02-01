"""A2A HTTP agent wrapper using shared Observation/Action types."""

import os
from typing import Dict, Any, Union

import requests

from core.schema import action_from_dict
from core.types import Action, Observation


class A2AClient:
    def __init__(self, url: str):
        if not url:
            raise ValueError("A2AClient requires a URL")
        self.url = url.rstrip("/")

    def send_action(self, observation: Union[Observation, Dict[str, Any]]) -> Dict[str, Any]:
        timeout = float(os.environ.get("A2A_TIMEOUT", "30"))
        payload = observation.to_dict() if isinstance(observation, Observation) else observation
        resp = requests.post(self.url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()


class A2AAgent:
    """Adapter that exposes the AgentBase-style methods."""

    def __init__(self, name: str, role: str, seed: int, client: A2AClient):
        self.name = name
        self.role = role
        self.seed = seed
        self.client = client
        self.alive = True
        self.seer_checks = []

    def speak(self, obs: Observation) -> Action:
        action = self.client.send_action(obs)
        return action_from_dict(action)

    def vote(self, obs: Observation) -> Action:
        action = self.client.send_action(obs)
        return action_from_dict(action)

    def night_power(self, obs: Observation) -> Action:
        action = self.client.send_action(obs)
        return action_from_dict(action)

    def mark_dead(self) -> None:
        self.alive = False

    def update_seer_inspection(self, target: str, role: str) -> None:
        self.seer_checks.append({"target": target, "role": role})
