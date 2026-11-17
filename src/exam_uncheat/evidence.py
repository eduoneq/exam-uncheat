"""Append-only, hash-chained evidence ledger and verifier.

Each line of ledger.jsonl is::

    {"seq": n, "type": "...", "ts": "...", "data": {...}, "prev": "<sha256>", "h": "<sha256>"}

where h = sha256(prev + canonical_json({seq, type, ts, data})). Editing, deleting
or reordering any line breaks the chain. On session close a SHA256SUMS file
covers every file in the session directory.
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

GENESIS = "0" * 64
LEDGER = "ledger.jsonl"
SUMS = "SHA256SUMS"


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def record_hash(prev: str, rec: dict) -> str:
    body = {k: rec[k] for k in ("seq", "type", "ts", "data")}
    return hashlib.sha256((prev + canonical(body)).encode("utf-8")).hexdigest()


class Ledger:
    def __init__(self, directory: Path):
        self.dir = Path(directory)
        self.path = self.dir / LEDGER
        self._lock = threading.Lock()
        self.seq = 0
        self.head = GENESIS
        if self.path.exists():  # resume
            for line in self.path.read_text(encoding="utf-8").splitlines():
                rec = json.loads(line)
                self.seq, self.head = rec["seq"], rec["h"]

    def append(self, rtype: str, ts: str, data: dict) -> dict:
        with self._lock:
            rec = {"seq": self.seq + 1, "type": rtype, "ts": ts, "data": data, "prev": self.head}
            rec["h"] = record_hash(self.head, rec)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(canonical(rec) + "\n")
            self.seq, self.head = rec["seq"], rec["h"]
            return rec


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_sums(directory: Path) -> Path:
    directory = Path(directory)
    lines = [f"{sha256_file(p)}  {p.name}" for p in sorted(directory.iterdir())
             if p.is_file() and p.name != SUMS]
    out = directory / SUMS
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def read_ledger(directory: Path) -> list[dict]:
    p = Path(directory) / LEDGER
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify(directory: Path) -> tuple[bool, list[str]]:
    """Verify hash chain and SHA256SUMS. Returns (ok, messages)."""
    directory = Path(directory)
    msgs: list[str] = []
    ok = True
    p = directory / LEDGER
    if not p.exists():
        return False, [f"missing {LEDGER}"]
    prev = GENESIS
    n = 0
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            return False, [f"line {i}: not JSON"]
        if rec.get("seq") != n + 1:
            ok = False
            msgs.append(f"line {i}: sequence gap (expected {n + 1}, got {rec.get('seq')})")
        if rec.get("prev") != prev:
            ok = False
            msgs.append(f"line {i}: prev hash mismatch")
        if record_hash(rec.get("prev", ""), rec) != rec.get("h"):
            ok = False
            msgs.append(f"line {i}: record hash mismatch (content altered)")
        prev, n = rec.get("h", ""), rec.get("seq", n + 1)
    msgs.append(f"ledger: {n} records, head {prev[:16]}…")
    sums = directory / SUMS
    if sums.exists():
        for line in sums.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, name = line.split("  ", 1)
            f = directory / name
            if not f.exists():
                ok = False
                msgs.append(f"SHA256SUMS: missing file {name}")
            elif sha256_file(f) != digest:
                ok = False
                msgs.append(f"SHA256SUMS: {name} modified")
        msgs.append("SHA256SUMS checked")
    else:
        msgs.append("SHA256SUMS absent (session not closed)")
    return ok, msgs
