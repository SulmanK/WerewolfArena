"""Agent factory/registry."""

from typing import Any


def get_agent(kind: str, **kwargs: Any):
    kind_norm = (kind or "").strip().lower()
    if kind_norm in ("scripted", "baseline", "npc"):
        from agents.npc_agent import NpcAgent

        return NpcAgent(**kwargs)
    if kind_norm in ("a2a", "http"):
        from agents.a2a_agent import A2AAgent, A2AClient

        url = kwargs.pop("url", None)
        client = kwargs.pop("client", None) or A2AClient(url)
        return A2AAgent(client=client, **kwargs)
    raise ValueError(f"Unknown agent kind: {kind}")
