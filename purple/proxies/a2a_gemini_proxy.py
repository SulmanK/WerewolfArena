"""A2A proxy to Gemini (gemini-2.5-flash-lite by default).

Usage:
  GEMINI_API_KEY=... python purple/proxies/a2a_gemini_proxy.py --host 0.0.0.0 --port 8080 \
      --model gemini-2.5-flash-lite --temperature 0.2 --max-output-tokens 256

Notes:
- Expects A2A-style observations and returns action JSON: speak/vote/night_power/noop.
- Default model: gemini-2.5-flash-lite; override via --model or env MODEL_ID.
- Not used in CI; offline scripted remains default in runner.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
import re
from typing import Dict

import google.generativeai as genai

DEFAULT_MODEL = os.environ.get("MODEL_ID", "gemini-2.5-flash-lite")
DEFAULT_TEMPERATURE = float(os.environ.get("MODEL_TEMPERATURE", "0.0"))
DEFAULT_MAX_OUTPUT_TOKENS = int(os.environ.get("MODEL_MAX_TOKENS", "256"))
DEFAULT_TOP_P = float(os.environ.get("MODEL_TOP_P", "1.0"))
DEFAULT_TOP_K = int(os.environ.get("MODEL_TOP_K", "1"))
DEFAULT_CANDIDATE_COUNT = int(os.environ.get("MODEL_CANDIDATE_COUNT", "1"))
DEFAULT_DETERMINISTIC = True


def format_prompt(obs: Dict, strict: bool = False) -> str:
    role = obs.get("role")
    phase = obs.get("phase")
    public = obs.get("public_debate", [])
    remaining = obs.get("remaining_players", [])
    graveyard = obs.get("graveyard", [])
    private = obs.get("private", {})

    # Exemplars per phase
    if phase == "day":
        exemplar = (
            '{"type": "speak", "content": "I suspect <name> because they said \'<quote>\' and it conflicts with <reason>."}\n'
            'If fewer than 3 prior lines, you may ask for info instead of accusing.'
        )
        action_hint = 'Produce exactly one JSON object with keys "type" and "content". After 3+ debate lines, name a player and cite a phrase/reason. You may also output {"type":"noop"} to skip.'
    elif phase == "day_vote":
        exemplar = f'{{"type": "vote", "target": "{remaining[0] if remaining else ""}", "content": "Voting <name> because <short reason referencing debate>."}}'
        action_hint = 'Produce exactly one JSON object with keys "type", "target", and "content". Target must be one of the allowed names. You may also output {"type":"noop"} to skip.'
    else:
        exemplar = f'{{"type": "night_power", "target": "{remaining[0] if remaining else ""}"}}'
        action_hint = 'Produce exactly one JSON object with keys "type" and "target". Target must be one of the allowed names. You may also output {"type":"noop"} to skip.'

    role_hint = "As a Werewolf, avoid targeting or accusing other Werewolves; prefer non-wolf targets." if role == "Werewolf" and phase in ("day", "day_vote", "night") else ""
    if role == "Werewolf":
        style_hint = "Blend in, sound like a villager, and use mild, plausible suspicions. Avoid overconfident claims."
    elif role == "Seer":
        style_hint = "If you have seer_checks, you may hint or claim; otherwise hedge and avoid certainty."
    elif role == "Doctor":
        style_hint = "Encourage caution and information-gathering; avoid hard claims."
    else:
        style_hint = "You do not know roles; use hedged language and avoid certainty."

    strict_hint = "Return ONLY the JSON object, no prose, no code fences." if strict else "Return JSON only; no leading/trailing prose."

    lines = [
        f"You are {obs.get('name')} playing role {role}.",
        f"Round: {obs.get('round')} Phase: {phase}.",
        f"Remaining players: {remaining}",
        f"Allowed targets (use exact spelling): {remaining}",
        f"Graveyard: {graveyard}",
        f"Debate so far: {public}",
        f"Private info: {private}",
        "Constraint: do not assert certainty about roles unless supported by private info.",
        style_hint,
        "If you are a Werewolf: use light misdirection (agree/deflect, ask a question, offer an alternative suspect) to avoid looking too cooperative.",
        action_hint,
        f"Example: {exemplar}",
        role_hint,
        strict_hint,
        'Schema: {"type": "speak|vote|night_power|noop", "content": str?, "target": str?}.',
    ]
    return "\n".join(lines)


def call_model(
    model: str, temperature: float, max_tokens: int, obs: Dict, *, strict: bool = False
) -> tuple[Dict, str, str]:
    prompt = format_prompt(obs, strict=strict)
    # Deterministic-ish settings for Gemini: clamp sampling and candidates.
    if DEFAULT_DETERMINISTIC:
        temperature = 0.0
        top_p = 1.0
        top_k = 1
        candidate_count = 1
    else:
        top_p = DEFAULT_TOP_P
        top_k = DEFAULT_TOP_K
        candidate_count = DEFAULT_CANDIDATE_COUNT
    response = genai.GenerativeModel(model).generate_content(
        prompt,
        generation_config={
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "top_p": top_p,
            "top_k": top_k,
            "candidate_count": candidate_count,
        },
    )
    # Parse JSON action from text
    text = response.text or "{}"
    try:
        action = json.loads(text)
    except json.JSONDecodeError:
        # fallback: try to extract JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            action = json.loads(text[start : end + 1])
        else:
            action = {"type": "speak", "content": text.strip()[:200]}
    return action, text, prompt


def validate_action(obs: Dict, action: Dict) -> str:
    """Return empty string if valid, else error message."""
    phase = obs.get("phase")
    remaining = obs.get("remaining_players", [])
    t = action.get("type")
    if t not in ("speak", "vote", "night_power", "noop"):
        return "invalid type"
    if t == "noop":
        if phase == "night":
            # Allow skip at night (e.g., Doctor).
            return ""
        return "noop only allowed at night"
    if phase == "day":
        if t != "speak" or not action.get("content"):
            return "day requires speak with content"
    elif phase == "day_vote":
        if t != "vote" or not action.get("target") or action.get("target") not in remaining:
            return "day_vote requires vote with target in remaining_players"
    else:
        if t != "night_power" or not action.get("target") or action.get("target") not in remaining:
            return "night requires night_power with target in remaining_players"
        # No role-specific validation here to keep parity with benchmark rules.
    return ""


def normalize_target(action: Dict, remaining: list) -> Dict:
    """Normalize target to a valid remaining player when possible."""
    if not remaining:
        return action
    target = action.get("target")
    if not target:
        return action
    if target in remaining:
        return action
    # Case-insensitive match or trimmed match.
    target_norm = target.strip().lower()
    for name in remaining:
        if name.lower() == target_norm:
            action["target"] = name
            return action
    return action


def ensure_target(obs: Dict, action: Dict) -> Dict:
    """Ensure target is present for phases that require it."""
    phase = obs.get("phase")
    if phase not in ("day_vote", "night"):
        return action
    if action.get("type") == "noop":
        return action
    remaining = obs.get("remaining_players", [])
    if action.get("target"):
        if phase == "night":
            role = obs.get("role")
            if role == "Werewolf":
                wolves = set((obs.get("private") or {}).get("wolves") or [])
                if action["target"] in wolves:
                    non_wolves = [p for p in remaining if p not in wolves]
                    if non_wolves:
                        action["target"] = non_wolves[0]
        return action
    if not remaining:
        return action
    me = obs.get("name")
    fallback = next((p for p in remaining if p != me), remaining[0])
    action["target"] = fallback
    return action


def force_phase_type(obs: Dict, action: Dict) -> Dict:
    """Force action type to the required phase-specific type."""
    if action.get("type") == "noop":
        return action
    phase = obs.get("phase")
    if phase == "day":
        if action.get("type") != "speak":
            action["type"] = "speak"
        return action
    if phase == "day_vote":
        if action.get("type") != "vote":
            action["type"] = "vote"
        return action
    if phase == "night":
        if action.get("type") != "night_power":
            action["type"] = "night_power"
        return action
    return action


def reduce_quiet_repeat(content: str, recent: list) -> str:
    """Reduce repetitive 'quiet' rationales by swapping in low-signal phrasing."""
    markers = [
        r"\bquiet\b",
        r"\bsilence\b",
        r"not said much",
        r"hasn't said much",
        r"hasnt said much",
        r"not talking much",
    ]
    if not any(re.search(m, content, flags=re.IGNORECASE) for m in markers):
        return content
    if "quiet" in recent:
        content = re.sub(r"\bquiet\b", "hard to read", content, flags=re.IGNORECASE)
        content = re.sub(r"\bsilence\b", "low signal", content, flags=re.IGNORECASE)
        content = re.sub(r"not said much", "not giving much to go on", content, flags=re.IGNORECASE)
        content = re.sub(r"hasn't said much", "hasn't given much to go on", content, flags=re.IGNORECASE)
        content = re.sub(r"hasnt said much", "hasn't given much to go on", content, flags=re.IGNORECASE)
        content = re.sub(r"not talking much", "not giving much to go on", content, flags=re.IGNORECASE)
    return content


def coerce_invalid_target(obs: Dict, action: Dict) -> Dict:
    """If target is invalid, coerce to a deterministic safe target."""
    if action.get("type") == "noop":
        return action
    remaining = obs.get("remaining_players", [])
    if not remaining:
        return action
    if obs.get("phase") == "night" and obs.get("role") == "Werewolf":
        wolves = set((obs.get("private") or {}).get("wolves") or [])
        non_wolves = [p for p in remaining if p not in wolves]
        if non_wolves:
            if action.get("target") not in non_wolves:
                action["target"] = non_wolves[0]
                return action
    target = action.get("target")
    if target in remaining:
        return action
    me = obs.get("name")
    # Prefer non-self if possible.
    fallback = next((p for p in remaining if p != me), remaining[0])
    action["target"] = fallback
    return action


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.rstrip("/") == "/.well-known/agent-card.json":
            card = self.server.agent_card()
            body = json.dumps(card).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw)
            obs = extract_observation(payload)
        except Exception:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"invalid json")
            return
        try:
            seed = obs.get("seed", -1)
            round_num = obs.get("round")
            phase = obs.get("phase")
            if phase == "night" and round_num == 0:
                prev_round = self.server.last_round_by_seed.get(seed)
                if prev_round is not None and prev_round > 0:
                    self.server.last_speak = {k: v for k, v in self.server.last_speak.items() if k[0] != seed}
                self.server.last_round_by_seed[seed] = 0
            elif isinstance(round_num, int):
                prev_round = self.server.last_round_by_seed.get(seed, -1)
                self.server.last_round_by_seed[seed] = max(prev_round, round_num)

            print(f"[REQ] round={round_num} phase={phase} role={obs.get('role')} name={obs.get('name')}")
            print(f"[META] model={self.server.model} temp={self.server.temperature} max_tokens={self.server.max_tokens}")
            action, raw_text, prompt = call_model(
                self.server.model, self.server.temperature, self.server.max_tokens, obs
            )
            if self.server.log_full_prompt:
                print(f"[PROMPT] {prompt}")
            else:
                digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
                print(f"[PROMPT] sha256={digest} len={len(prompt)}")
            action = normalize_target(action, obs.get("remaining_players", []))
            action = force_phase_type(obs, action)
            action = ensure_target(obs, action)
            err = validate_action(obs, action)
            if err:
                # one-shot repair with strict template
                print(f"[WARN] validate failed '{err}', attempting repair")
                print(f"[WARN] raw_model='{raw_text[:300]}'")
                print(f"[WARN] parsed_action={action}")
                action, raw_text, prompt = call_model(
                    self.server.model, self.server.temperature, self.server.max_tokens, obs, strict=True
                )
                if self.server.log_full_prompt:
                    print(f"[PROMPT] {prompt}")
                else:
                    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
                    print(f"[PROMPT] sha256={digest} len={len(prompt)}")
                action = normalize_target(action, obs.get("remaining_players", []))
                action = force_phase_type(obs, action)
                action = ensure_target(obs, action)
                err = validate_action(obs, action)
            if err:
                # last-chance target coercion before fallback
                action = coerce_invalid_target(obs, action)
                err = validate_action(obs, action)
            if err:
                # fallback scripted safe line instead of 500
                print(f"[FALLBACK] using scripted action due to '{err}'")
                action = self.server.safe_fallback(obs)
            # Final safety: ensure wolves don't target wolves at night.
            if obs.get("phase") == "night" and obs.get("role") == "Werewolf":
                wolves = set((obs.get("private") or {}).get("wolves") or [])
                remaining = obs.get("remaining_players", [])
                if action.get("target") in wolves:
                    non_wolves = [p for p in remaining if p not in wolves]
                    if non_wolves:
                        old = action.get("target")
                        action["target"] = non_wolves[0]
                        print(f"[WARN] coerced wolf night target {old} -> {action['target']}")
            # Strip content on night actions to keep schema tight.
            if action.get("type") == "night_power":
                action.pop("content", None)
            print(f"[RES] action={action}")
            # simple per-speaker de-dup for day speak; if dup, lightly adjust content
            if obs.get("phase") == "day" and action.get("type") == "speak":
                key = (obs.get("seed", -1), obs.get("name"), obs.get("round"))
                last = self.server.last_speak.get(key)
                content = (action.get("content") or "")
                seed = obs.get("seed", -1)
                recent = self.server.recent_reasons.setdefault(seed, [])
                content = reduce_quiet_repeat(content, recent)
                if any(k in content.lower() for k in ("quiet", "silence", "not said much", "hasn't said much", "hasnt said much", "not talking much")):
                    recent.append("quiet")
                    self.server.recent_reasons[seed] = recent[-5:]
                if last and last.strip().lower() == content.strip().lower():
                    print("[WARN] duplicate speak content for same speaker/round; adjusting")
                    # light paraphrase to avoid exact dup
                    content = content + " Adding: want to hear from others before deciding."
                    action["content"] = content
                # mark low-signal quiet-only lines
                if content.strip().lower() in ("quiet", "he is quiet", "she is quiet", "they are quiet"):
                    action["content"] = "[low-signal] " + content
                self.server.last_speak[key] = content
            if action.get("type") == "vote" and action.get("content"):
                seed = obs.get("seed", -1)
                recent = self.server.recent_reasons.setdefault(seed, [])
                content = reduce_quiet_repeat(action.get("content") or "", recent)
                if any(k in content.lower() for k in ("quiet", "silence", "not said much", "hasn't said much", "hasnt said much", "not talking much")):
                    recent.append("quiet")
                    self.server.recent_reasons[seed] = recent[-5:]
                action["content"] = content
        except Exception as e:
            print(f"[ERR] {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))
            return
        body = json.dumps(wrap_a2a_response(payload, action)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except ConnectionAbortedError:
            print("[WARN] client closed connection before response was sent")

    def log_message(self, format, *args):
        return


def main():
    parser = argparse.ArgumentParser(description="A2A proxy to Gemini")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--max-output-tokens", type=int, default=DEFAULT_MAX_OUTPUT_TOKENS)
    parser.add_argument("--log-dir", default="", help="Optional directory to write a timestamped log file")
    parser.add_argument("--card-url", default="", help="Ignored (compat with AgentBeats compose)")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is required")
    genai.configure(api_key=api_key)

    if args.log_dir:
        os.makedirs(args.log_dir, exist_ok=True)
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(args.log_dir, f"gemini_proxy_{ts}.log")
        log_file = open(log_path, "a", encoding="utf-8", buffering=1)
        sys.stdout = log_file
        sys.stderr = log_file
        print(f"[LOG] writing to {log_path}")

    server = HTTPServer((args.host, args.port), Handler)
    server.model = args.model
    server.temperature = args.temperature
    server.max_tokens = args.max_output_tokens
    server.last_speak = {}  # {(name, round): content}
    server.last_round_by_seed = {}  # {seed: last_round}
    server.recent_reasons = {}  # {seed: [reason_keys]}
    server.log_full_prompt = os.environ.get("LOG_FULL_PROMPT") == "1"
    server.safe_fallback = safe_fallback_action
    server.agent_card = build_agent_card
    genai_version = getattr(genai, "__version__", "unknown")
    print(
        f"Gemini proxy listening on {args.host}:{args.port} model={args.model} "
        f"temp={args.temperature} max_tokens={args.max_output_tokens} genai={genai_version} "
        f"key_present={'yes' if api_key else 'no'}"
    )
    server.serve_forever()


def safe_fallback_action(obs: Dict) -> Dict:
    """Offline safe action when model/validation fails."""
    phase = obs.get("phase")
    remaining = obs.get("remaining_players", [])
    me = obs.get("name")
    # choose a target that's not self if possible
    target = next((p for p in remaining if p != me), remaining[0] if remaining else None)
    if phase == "day":
        return {"type": "speak", "content": "Listening for evidence; no strong read yet."}
    if phase == "day_vote":
        return {"type": "vote", "target": target or (remaining[0] if remaining else "")}
    return {"type": "night_power", "target": target or (remaining[0] if remaining else "")}


def extract_observation(payload: Dict) -> Dict:
    """Allow raw observation or minimal A2A-style envelope."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be object")
    if payload.get("jsonrpc") and isinstance(payload.get("params"), dict):
        msg = payload["params"].get("message") or {}
        parts = msg.get("parts") or []
        if parts:
            part = parts[0]
            if isinstance(part, dict):
                if "data" in part:
                    return part["data"]
                if "text" in part:
                    return json.loads(part["text"])
                if part.get("type") == "data" and "data" in part:
                    return part["data"]
    return payload


def wrap_a2a_response(payload: Dict, action: Dict) -> Dict:
    """Return raw action or minimal JSON-RPC response if envelope detected."""
    if isinstance(payload, dict) and payload.get("jsonrpc") and "id" in payload:
        return {
            "jsonrpc": "2.0",
            "id": payload.get("id"),
            "result": {
                "status": "completed",
                "action": action,
            },
        }
    return action


def build_agent_card() -> Dict:
    """Minimal agent-card.json for A2A discovery."""
    return {
        "name": "gemini-proxy",
        "description": "Minimal A2A-compatible proxy to Gemini",
        "url": "",
        "version": "0.1.0",
        "capabilities": {"streaming": False},
        "defaultInputModes": ["text", "data"],
        "defaultOutputModes": ["text", "data"],
        "skills": [
            {
                "id": "werewolf-player",
                "name": "Werewolf Player",
                "description": "Responds to werewolf observations with speak/vote/night_power/noop",
                "tags": ["gaming", "social-deduction"],
            }
        ],
    }


if __name__ == "__main__":
    main()
