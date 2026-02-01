"""Base interface for purple agents."""

from abc import ABC, abstractmethod
from core.types import Action, Observation


class AgentBase(ABC):
    @abstractmethod
    def speak(self, obs: Observation) -> Action:
        raise NotImplementedError

    @abstractmethod
    def vote(self, obs: Observation) -> Action:
        raise NotImplementedError

    @abstractmethod
    def night_power(self, obs: Observation) -> Action:
        raise NotImplementedError
