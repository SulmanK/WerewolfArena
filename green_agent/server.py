"""
Green agent A2A server for AgentBeats evaluation.

Runs the benchmark.agent_vs_npc pipeline using the provided purple agent endpoint.
"""

import argparse
import json
import os
import subprocess
import sys
from typing import Any, Dict, Optional

import uvicorn
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import AgentCard, AgentCapabilities, AgentSkill, Part, DataPart
from a2a.utils import new_task, new_agent_text_message
from core.config import RunConfig


def _get_message_text(context: RequestContext) -> str:
    msg = context.message
    if not msg:
        return ""
    parts = msg.parts or []
    for part in parts:
        root = getattr(part, "root", None)
        if root is None:
            continue
        if hasattr(root, "text") and root.text:
            return root.text
        if hasattr(root, "data") and root.data is not None:
            return json.dumps(root.data)
    return ""


def _extract_participant_endpoint(payload: Dict[str, Any]) -> Optional[str]:
    participant = payload.get("participant")
    if isinstance(participant, dict):
        endpoint = participant.get("endpoint") or participant.get("url")
        if endpoint:
            return str(endpoint)
    elif isinstance(participant, str):
        return participant

    participants = payload.get("participants")
    if isinstance(participants, list):
        for entry in participants:
            if isinstance(entry, dict):
                endpoint = entry.get("endpoint") or entry.get("url")
                if endpoint:
                    return str(endpoint)
            elif isinstance(entry, str):
                return entry
    elif isinstance(participants, dict):
        for value in participants.values():
            if isinstance(value, dict):
                endpoint = value.get("endpoint") or value.get("url")
                if endpoint:
                    return str(endpoint)
            elif isinstance(value, str):
                return value

    for key in ("participant_endpoint", "endpoint", "purple_agent_url"):
        if key in payload and payload[key]:
            return str(payload[key])

    env_endpoint = os.environ.get("PURPLE_AGENT_URL")
    if env_endpoint:
        return env_endpoint

    return None


def _run_agent_vs_npc(payload: Dict[str, Any]) -> Dict[str, Any]:
    participant = _extract_participant_endpoint(payload)
    if not participant:
        raise ValueError(
            "Missing required participant endpoint. Expected 'participant' or "
            "'participants' in payload, or PURPLE_AGENT_URL env var."
        )

    config = payload.get("config", {})
    defaults = RunConfig()
    num_games = int(config.get("num_games", config.get("num_tasks", defaults.num_games)))
    shuffle_seed = int(config.get("shuffle_seed", defaults.shuffle_seed))
    max_rounds = int(config.get("max_rounds", defaults.max_rounds))
    max_turns = int(config.get("max_turns", defaults.max_turns))
    role_weights = str(config.get("role_weights", ""))
    seed_start = int(config.get("seed_start", defaults.seed_start))

    output_path = config.get("output", "/app/results/agentbeats_results.json")
    log_dir = config.get("log_dir", "/app/results/agentbeats_logs")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "benchmark.agent_vs_npc",
        "--a2a-endpoint",
        participant,
        "--num-games",
        str(num_games),
        "--shuffle-seed",
        str(shuffle_seed),
        "--max-rounds",
        str(max_rounds),
        "--max-turns",
        str(max_turns),
        "--seed-start",
        str(seed_start),
        "--output",
        output_path,
        "--log-dir",
        log_dir,
    ]
    if role_weights:
        cmd.extend(["--role-weights", role_weights])

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"agent_vs_npc failed (code {proc.returncode}): {proc.stderr.strip()}"
        )

    # Prefer output file, fall back to stdout JSON.
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # Try to parse last JSON object from stdout.
    lines = [l for l in proc.stdout.splitlines() if l.strip()]
    if lines:
        return json.loads(lines[-1])
    raise RuntimeError("No output produced by agent_vs_npc")


class WerewolfGreenExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work()

        try:
            raw = _get_message_text(context)
            payload = json.loads(raw) if raw else {}
            result = _run_agent_vs_npc(payload)

            await updater.add_artifact(
                [Part(root=DataPart(kind="data", data=result))]
            )
            await updater.complete()
        except Exception as e:
            await updater.failed(new_agent_text_message(f"Green agent error: {e}"))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError


def main() -> None:
    parser = argparse.ArgumentParser(description="Werewolf Green Agent (A2A)")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9009)
    # Accept --card-url for AgentBeats-generated compose compatibility.
    parser.add_argument("--card-url", type=str, default="", help="Public URL for agent card (overrides env)")
    args = parser.parse_args()

    skill = AgentSkill(
        id="werewolf-evaluator",
        name="Werewolf Evaluator",
        description="Evaluates a purple agent against NPCs and returns scorecard JSON",
        tags=["gaming", "evaluation", "social-deduction"],
    )

    public_url = args.card_url.strip() or os.environ.get("GREEN_AGENT_PUBLIC_URL", "").strip()
    card_url = public_url or f"http://{args.host}:{args.port}"

    card = AgentCard(
        name="Werewolf Green Agent",
        version="1.0.0",
        description="Green agent for AgentBeats Werewolf benchmark",
        url=card_url,
        protocol_version="0.3.0",
        skills=[skill],
        capabilities=AgentCapabilities(streaming=False),
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=WerewolfGreenExecutor(),
        task_store=InMemoryTaskStore(),
    )
    app = A2AStarletteApplication(
        agent_card=card,
        http_handler=request_handler,
    )

    uvicorn.run(app.build(), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
