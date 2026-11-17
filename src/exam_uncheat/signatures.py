"""Signature DB loader and matcher (exam-uncheat.signature/v1)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .paths import signatures_dir
from .schema import validate


def _ascii(hexstr: str) -> str:
    try:
        raw = bytes.fromhex(hexstr)
    except ValueError:
        return ""
    return "".join(chr(b) if 32 <= b < 127 else "." for b in raw)


def resolve(evt: dict, path: str) -> Any:
    attrs = evt.get("attrs", {})
    if path == "attrs.mfg_data_ascii":
        return _ascii(attrs.get("mfg_data_hex", ""))
    if path == "attrs.service_data_ascii":
        return " ".join(_ascii(v) for v in attrs.get("service_data", {}).values() if isinstance(v, str))
    cur: Any = evt
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _cond(evt: dict, c: dict) -> bool:
    if "all" in c and not all(_cond(evt, x) for x in c["all"]):
        return False
    if "any" in c and not any(_cond(evt, x) for x in c["any"]):
        return False
    if "field" not in c:
        return True
    v = resolve(evt, c["field"])
    if "exists" in c:
        return (v is not None) == c["exists"]
    if v is None:
        return False
    if "eq" in c:
        return v == c["eq"]
    if "in" in c:
        return v in c["in"]
    if "contains" in c:
        needle = c["contains"]
        if isinstance(v, dict):
            return str(needle).lower() in (str(k).lower() for k in v)
        if isinstance(v, list):
            return str(needle).lower() in (str(x).lower() for x in v)
        return str(needle) in str(v)
    if "regex" in c:
        return re.search(c["regex"], str(v)) is not None
    if "prefix" in c:
        return str(v).startswith(c["prefix"])
    if "hex_prefix" in c:
        return str(v).lower().startswith(c["hex_prefix"].lower())
    return False


@dataclass
class SignatureDB:
    signatures: list[dict] = field(default_factory=list)
    files: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, directory: Path | None = None) -> "SignatureDB":
        directory = Path(directory or signatures_dir())
        db = cls()
        seen = set()
        for p in sorted(directory.glob("*.yaml")):
            doc = yaml.safe_load(p.read_text(encoding="utf-8"))
            errs = validate(doc, "signature.schema.json")
            if errs:
                raise ValueError(f"{p.name}: invalid signature file: {errs[:3]}")
            for s in doc["signatures"]:
                if s["id"] in seen:
                    raise ValueError(f"duplicate signature id {s['id']}")
                seen.add(s["id"])
                db.signatures.append(s)
            db.files.append(p.name)
        return db

    def match(self, evt: dict) -> list[dict]:
        out = []
        for s in self.signatures:
            kinds = s["match"]["kind"]
            kinds = [kinds] if isinstance(kinds, str) else kinds
            if evt.get("kind") not in kinds:
                continue
            if _cond(evt, {k: v for k, v in s["match"].items() if k in ("all", "any")}):
                out.append(s)
        return sorted(out, key=lambda s: -s["weight"])

    def get(self, sig_id: str) -> dict | None:
        return next((s for s in self.signatures if s["id"] == sig_id), None)
