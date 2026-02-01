"""A2A bridge/server (minimal functional HTTP JSON)."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from benchmark import protocol
from agents.npc_agent import NpcAgent
from core.schema import build_observation


class A2AHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            obs = json.loads(raw)
            protocol.validate_observation(obs)
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))
            return

        # Generate a deterministic scripted response as a fallback baseline
        role = obs.get("role", "Villager")
        name = obs.get("name", "Agent")
        seed = obs.get("seed", 0)
        agent = NpcAgent(name=name, role=role, seed=seed)
        phase = obs.get("phase", "day")
        observation = build_observation(
            round_num=int(obs.get("round", 0)),
            phase=phase,
            role=role,
            name=name,
            seed=seed,
            remaining_players=obs.get("remaining_players", []),
            graveyard=obs.get("graveyard", []),
            public_debate=obs.get("public_debate", []),
            private=obs.get("private", {}),
        )
        if phase == "day":
            action = agent.speak(observation).to_dict()
        elif phase == "day_vote":
            action = agent.vote(observation).to_dict()
        else:
            action = agent.night_power(observation).to_dict()

        body = json.dumps(action).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return  # silence default logging


def start_server(host: str = "0.0.0.0", port: int = 8080):
    server = HTTPServer((host, port), A2AHandler)
    print(f"Starting A2A server on {host}:{port}")
    server.serve_forever()
