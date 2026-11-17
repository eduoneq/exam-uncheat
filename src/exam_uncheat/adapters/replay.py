"""Replay adapter: plays a JSONL file of events (and control lines) in real
or accelerated time. Used for demos, CI and field-recording playback."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .base import Adapter


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


class ReplayAdapter(Adapter):
    name = "replay"

    def __init__(self, sink, items: list[dict], speed: float = 1.0):
        super().__init__(sink)
        self.items, self.speed = items, speed

    def run(self) -> None:
        start = time.monotonic()
        for obj in self.items:
            if self.stopped:
                return
            off = obj.get("offset_s")
            if off is not None and self.speed > 0:
                delay = start + off / self.speed - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
            self.emit(obj)
