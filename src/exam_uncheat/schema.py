"""Event schema validation and normalization (exam-uncheat.event/v1)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator

from .paths import spec_dir

EVENT_SCHEMA_ID = "exam-uncheat.event/v1"


@lru_cache(maxsize=None)
def _validator(name: str) -> Draft202012Validator:
    with open(spec_dir() / name, encoding="utf-8") as f:
        return Draft202012Validator(json.load(f))


def validate(obj: Any, schema_file: str = "event.schema.json") -> list[str]:
    """Return a list of human-readable validation errors (empty = valid)."""
    errs = []
    for e in sorted(_validator(schema_file).iter_errors(obj), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in e.path) or "<root>"
        errs.append(f"{loc}: {e.message}")
    return errs


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def parse_ts(ts: str) -> float:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


def normalize(evt: dict) -> dict:
    """Fill hub-side fields. Mutates and returns the event."""
    evt.setdefault("event_id", uuid.uuid4().hex)
    if "ts" not in evt:
        evt["ts"] = now_iso()
    attrs = evt.setdefault("attrs", {})
    if evt.get("kind") == "ble.adv":
        if "service_uuids" in attrs:
            attrs["service_uuids"] = [str(u).lower() for u in attrs["service_uuids"]]
        if "service_data" in attrs:
            attrs["service_data"] = {str(k).lower(): v for k, v in attrs["service_data"].items()}
        if "mfg_data_hex" in attrs:
            # keep at most 32 bytes of manufacturer data
            attrs["mfg_data_hex"] = attrs["mfg_data_hex"].lower()[:64]
    return evt
