"""Exam session: ingest pipeline, evidence ledger, proctor actions, close & report."""
from __future__ import annotations

import json
import re
import shutil
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from . import __version__
from .engine import Engine, EngineConfig
from .evidence import Ledger, write_sums
from .privacy import PrivacyGate
from .schema import normalize, now_iso, parse_ts, validate
from .signatures import SignatureDB

DEFAULT_RETENTION_DAYS = 30
DISCLAIMER_KO = "본 자료는 감독관 판단을 돕는 참고 기록이며, 부정행위 여부를 판정하지 않습니다."


def _slug(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣_-]+", "-", s or "").strip("-")[:32] or "x"


class Session:
    def __init__(self, data_dir: Path, meta: dict, sigdb: SignatureDB,
                 engine_cfg: EngineConfig | None = None, key: bytes | None = None,
                 retention_days: int = DEFAULT_RETENTION_DAYS, started_at: str | None = None):
        self.meta = {k: str(v) for k, v in (meta or {}).items() if v is not None}
        self.sigdb = sigdb
        self.gate = PrivacyGate(key)
        self.engine = Engine(engine_cfg)
        self.lock = threading.RLock()
        self.started_at = started_at or now_iso()
        self.session_id = uuid.uuid4().hex[:8]
        day = self.started_at[:10]
        name = "_".join([day, _slug(self.meta.get("site", "site")), _slug(self.meta.get("room", "room")),
                         _slug(self.meta.get("period", "p")), self.session_id])
        self.dir = Path(data_dir) / "sessions" / name
        self.dir.mkdir(parents=True, exist_ok=False)
        self.ledger = Ledger(self.dir)
        self.sensors: dict[str, dict] = {}
        self.rejected = 0
        self.accepted = 0
        self.closed = False
        self.retention_days = retention_days
        self.manifest = {
            "schema": "exam-uncheat.manifest/v1",
            "session_id": self.session_id,
            "hub_version": __version__,
            "started_at": self.started_at,
            "meta": self.meta,
            "signature_db": {"files": sigdb.files, "count": len(sigdb.signatures)},
            "session_key_fingerprint": self.gate.fingerprint,
            "retention_days": retention_days,
            "delete_after": (datetime.fromisoformat(self.started_at) + timedelta(days=retention_days)).isoformat(),
            "disclaimer": DISCLAIMER_KO,
        }
        self._write_manifest()
        self.ledger.append("session_start", self.started_at, {"meta": self.meta, "phase": "baseline"})

    # ------------------------------------------------------------------
    @property
    def phase(self) -> str:
        return self.engine.phase

    def _write_manifest(self) -> None:
        self.manifest["sensors"] = self.sensors
        (self.dir / "manifest.json").write_text(json.dumps(self.manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def register_sensor(self, hello: dict) -> None:
        with self.lock:
            sid = hello.get("sensor_id") or "unknown"
            info = {k: hello.get(k) for k in ("driver", "driver_version", "hw", "capabilities", "bands", "tx_capable")}
            if self.sensors.get(sid) != info:
                self.sensors[sid] = info
                self._write_manifest()
                self.ledger.append("sensor", now_iso(), {"sensor_id": sid, **info})

    def start_exam(self, ts: str | None = None) -> dict:
        with self.lock:
            summary = self.engine.start_exam()
            (self.dir / "baseline.json").write_text(
                json.dumps({"summary": summary, "groups": self.engine.baseline}, ensure_ascii=False, indent=2),
                encoding="utf-8")
            self.ledger.append("phase", ts or now_iso(), {"phase": "exam", "baseline": summary})
            return summary

    def ingest(self, evt: dict) -> dict:
        """Validate → normalize → signature match (raw) → privacy scrub → engine → ledger."""
        if self.closed:
            raise RuntimeError("session closed")
        errs = validate(evt)
        if errs:
            with self.lock:
                self.rejected += 1
            return {"ok": False, "errors": errs[:5]}
        with self.lock:
            evt = normalize(dict(evt))
            sigs = self.sigdb.match(evt)                 # needs raw names/SSIDs, in memory only
            safe = self.gate.scrub(evt)
            safe["phase"] = self.phase
            if sigs:
                safe["signature_ids"] = [s["id"] for s in sigs]
            t = parse_ts(safe["ts"])
            sid = safe["sensor"]["id"]
            self.sensors.setdefault(sid, {"driver": safe["sensor"].get("driver")})
            self.ledger.append("event", safe["ts"], safe)
            changed = self.engine.observe(safe, t, sigs)
            for c in changed:
                rec = {k: v for k, v in c.items() if not k.startswith("_")}
                self.ledger.append("clue", c["ts_last"], {"change": c["_change"], **rec})
            self.accepted += 1
            return {"ok": True, "event_id": safe["event_id"], "clues": [c["clue_id"] for c in changed]}

    def add_action(self, action: dict, ts: str | None = None) -> dict:
        errs = validate(action, "action.schema.json")
        if errs:
            raise ValueError("; ".join(errs))
        with self.lock:
            if action["clue_id"] not in self.engine.clues:
                raise KeyError(action["clue_id"])
            rec = {"ts": ts or now_iso(), "actor_role": action.get("actor_role", "proctor"), **action}
            self.engine.add_decision(action["clue_id"], rec)
            self.ledger.append("action", rec["ts"], rec)
            return rec

    def status(self) -> dict:
        with self.lock:
            return {
                "session_id": self.session_id, "dir": str(self.dir), "phase": self.phase, "meta": self.meta,
                "started_at": self.started_at, "accepted": self.accepted, "rejected": self.rejected,
                "sensors": self.sensors, "closed": self.closed,
                "baseline": self.engine.baseline_summary() if self.phase == "exam" else None,
                "clue_counts": {lv: sum(1 for c in self.engine.clues.values() if c["level"] == lv)
                                for lv in ("urgent", "check", "info")},
            }

    def clues(self) -> list[dict]:
        with self.lock:
            order = {"urgent": 0, "check": 1, "info": 2}
            return sorted((dict(c) for c in self.engine.clues.values()),
                          key=lambda c: (order[c["level"]], c["t_first"]))

    def close(self, ts: str | None = None) -> dict:
        from .report import render_html, render_markdown
        with self.lock:
            if self.closed:
                return self.status()
            ts = ts or now_iso()
            summary = self.status()
            self.ledger.append("session_close", ts, {"summary": {k: summary[k] for k in
                                                                 ("accepted", "rejected", "clue_counts")},
                                                     "ledger_head_before_close": self.ledger.head})
            self.manifest["closed_at"] = ts
            self.manifest["ledger_head"] = self.ledger.head
            self._write_manifest()
            data = self.report_data()
            (self.dir / "report.md").write_text(render_markdown(data), encoding="utf-8")
            (self.dir / "report.html").write_text(render_html(data), encoding="utf-8")
            write_sums(self.dir)
            self.gate.destroy()   # pseudonyms can no longer be recomputed
            self.closed = True
            return self.status()

    def report_data(self) -> dict:
        with self.lock:
            return {"manifest": self.manifest, "status": self.status(), "clues": self.clues(),
                    "baseline": self.engine.baseline_summary(), "ledger_head": self.ledger.head,
                    "disclaimer": DISCLAIMER_KO}


def purge_expired(data_dir: Path, now: datetime | None = None) -> list[str]:
    """Delete closed sessions past their delete_after date. Returns removed dir names."""
    now = now or datetime.now().astimezone()
    removed = []
    root = Path(data_dir) / "sessions"
    if not root.exists():
        return removed
    for d in root.iterdir():
        m = d / "manifest.json"
        if not m.exists():
            continue
        man = json.loads(m.read_text(encoding="utf-8"))
        if man.get("closed_at") and datetime.fromisoformat(man["delete_after"]) <= now:
            shutil.rmtree(d)
            removed.append(d.name)
    return removed
