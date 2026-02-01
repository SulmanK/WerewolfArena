"""Shared logging helpers for JSONL outputs."""

import json
from pathlib import Path
from typing import Iterable


def write_jsonl(path: str, records: Iterable[dict]) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
