"""Baseline-vs-exam diffing, signature scoring and clue generation.

A *clue* is a hint for a human proctor, never a verdict.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

LEVELS = ("info", "check", "urgent")
LEVEL_KO = {"info": "참고", "check": "확인 권장", "urgent": "즉시 확인 권장"}


@dataclass
class EngineConfig:
    persist_s: float = 20.0          # signal must persist this long (or repeat) before a clue
    min_events: int = 3
    near_rssi_dbm: float = -70.0      # stronger than this → likely in room
    weak_rssi_dbm: float = -85.0      # weaker than this (peak) → capped at info
    combo_window_s: float = 180.0     # smart-glasses BLE + Wi-Fi Direct within this window
    rf_occupancy_delta: float = 0.2


@dataclass
class Group:
    key: str
    kind: str
    first_t: float
    last_t: float
    first_ts: str
    last_ts: str
    count: int = 0
    pids: set = field(default_factory=set)
    max_rssi: float | None = None
    sig_ids: list = field(default_factory=list)
    categories: set = field(default_factory=set)
    weight: int = 0
    zones: set = field(default_factory=set)
    sensors: set = field(default_factory=set)
    event_refs: list = field(default_factory=list)
    max_occupancy: float | None = None


def group_key(evt: dict, sigs: list[dict]) -> str | None:
    kind = evt["kind"]
    a = evt.get("attrs", {})
    pid = (evt.get("subject") or {}).get("pid", "")
    if kind == "sensor.health":
        return None
    if kind == "detector.alert":
        return f"det:{evt['event_id']}"
    if kind == "rf.energy":
        return f"rf:{evt.get('band', 'other')}:{a.get('f_start_mhz')}-{a.get('f_stop_mhz')}"
    if sigs:
        return f"sig:{sigs[0]['id']}"
    if kind == "ble.adv":
        svcs = ",".join(sorted(a.get("service_uuids", []) + list(a.get("service_data", {}).keys())))
        return f"ble:cid={a.get('company_id')}:svc={svcs}"
    if kind == "wifi.beacon":
        return f"ap:{a.get('ssid_pid') or a.get('bssid_pid') or pid}"
    if kind == "wifi.probe_req":
        return f"probe:{a.get('ie_fingerprint') or pid}"
    if kind == "wifi.station":
        return f"sta:{pid}"
    if kind == "wifi.p2p":
        return f"p2p:{pid}"
    if kind == "ble.conn_activity":
        return f"conn:{a.get('access_addr_hash') or pid}"
    return f"{kind}:{pid}"


def _reason_kind(r: str) -> str | None:
    for k in ("신호 강도 최고", "약한 신호", "같은 종류 신호 개수", "대역 점유율"):
        if r.startswith(k):
            return k
    if r.endswith("초 이상 지속"):
        return "duration"
    return None


class Engine:
    def __init__(self, cfg: EngineConfig | None = None):
        self.cfg = cfg or EngineConfig()
        self.phase = "baseline"
        self.baseline: dict[str, dict] = {}
        self.groups: dict[str, Group] = {}       # exam-phase groups
        self._bgroups: dict[str, Group] = {}     # baseline-phase groups
        self.clues: dict[str, dict] = {}         # clue_id -> clue
        self._clue_by_key: dict[str, str] = {}

    # ---- phases -------------------------------------------------------
    def start_exam(self) -> dict:
        for k, g in self._bgroups.items():
            self.baseline[k] = {
                "distinct": len(g.pids), "max_rssi": g.max_rssi, "count": g.count,
                "kind": g.kind, "max_occupancy": g.max_occupancy,
            }
        self.phase = "exam"
        return self.baseline_summary()

    def baseline_summary(self) -> dict:
        kinds: dict[str, int] = {}
        for v in self.baseline.values():
            kinds[v["kind"]] = kinds.get(v["kind"], 0) + 1
        return {"groups": len(self.baseline), "by_kind": kinds}

    # ---- observe ------------------------------------------------------
    def observe(self, evt: dict, t: float, sigs: list[dict]) -> list[dict]:
        """Feed one scrubbed event. Returns clues that were created or changed."""
        key = group_key(evt, sigs)
        if key is None:
            return []
        table = self._bgroups if self.phase == "baseline" else self.groups
        g = table.get(key)
        if g is None:
            g = table[key] = Group(key=key, kind=evt["kind"], first_t=t, last_t=t,
                                   first_ts=evt["ts"], last_ts=evt["ts"])
        g.last_t, g.last_ts = t, evt["ts"]
        g.count += 1
        pid = (evt.get("subject") or {}).get("pid")
        if pid:
            g.pids.add(pid)
        r = evt.get("rssi_dbm")
        if r is not None:
            g.max_rssi = r if g.max_rssi is None else max(g.max_rssi, r)
        for s in sigs:
            if s["id"] not in g.sig_ids:
                g.sig_ids.append(s["id"])
                g.categories.add(s["category"])
                g.weight = max(g.weight, s["weight"])
        loc = (evt.get("sensor") or {}).get("location") or {}
        if loc.get("zone"):
            g.zones.add(loc["zone"])
        g.sensors.add(evt["sensor"]["id"])
        if len(g.event_refs) < 50:
            g.event_refs.append(evt["event_id"])
        if evt["kind"] == "rf.energy":
            occ = evt.get("attrs", {}).get("occupancy")
            if occ is not None:
                g.max_occupancy = occ if g.max_occupancy is None else max(g.max_occupancy, occ)
        if self.phase != "exam":
            return []
        changed = []
        c = self._evaluate(g, sigs)
        if c:
            changed.append(c)
        changed.extend(self._combos(t))
        return changed

    # ---- scoring ------------------------------------------------------
    def _is_new(self, g: Group) -> tuple[bool, str]:
        b = self.baseline.get(g.key)
        if g.kind == "detector.alert":
            return True, "상용 탐지기 경보 또는 감독관 수동 입력"
        if g.kind == "rf.energy":
            if g.max_occupancy is None:
                return False, ""
            base = (b or {}).get("max_occupancy") or 0.0
            if g.max_occupancy >= base + self.cfg.rf_occupancy_delta:
                return True, f"대역 점유율 {base:.0%} → {g.max_occupancy:.0%} (빈 교실 대비 증가)"
            return False, ""
        if b is None:
            return True, "빈 교실 기준선에 없던 신호"
        if g.pids and len(g.pids) > (b.get("distinct") or 0):
            return True, f"같은 종류 신호 개수 증가 (기준선 {b.get('distinct')} → {len(g.pids)})"
        return False, ""

    def _evaluate(self, g: Group, sigs: list[dict]) -> dict | None:
        new, why = self._is_new(g)
        if not new:
            return None
        dur = g.last_t - g.first_t
        high_conf = any(s["confidence"] == "high" for s in sigs)
        instant = g.kind == "detector.alert"
        if not (instant or dur >= self.cfg.persist_s or (g.count >= self.cfg.min_events and high_conf)):
            return None
        reasons = [why]
        score = g.weight
        if g.kind == "detector.alert":
            score = max(score, 40)
        if g.kind == "rf.energy":
            score = max(score, 25)
        if dur >= self.cfg.persist_s:
            reasons.append(f"{int(dur)}초 이상 지속")
        if g.max_rssi is not None:
            if g.max_rssi >= self.cfg.near_rssi_dbm:
                score += 10
                reasons.append(f"신호 강도 최고 {g.max_rssi:.0f} dBm (교실 안 가능성)")
            elif g.max_rssi < self.cfg.weak_rssi_dbm:
                reasons.append(f"약한 신호 (최고 {g.max_rssi:.0f} dBm) — 복도·옆 교실 가능성")
        level = "urgent" if score >= 70 else "check" if score >= 25 else "info"
        if g.max_rssi is not None and g.max_rssi < self.cfg.weak_rssi_dbm:
            level = "info"
        return self._upsert(g, level, reasons)

    def _upsert(self, g: Group, level: str, reasons: list[str]) -> dict | None:
        cid = self._clue_by_key.get(g.key)
        if cid is None:
            cid = f"c-{len(self.clues) + 1:04d}"
            self._clue_by_key[g.key] = cid
            clue = {
                "clue_id": cid, "group": g.key, "kind": g.kind,
                "level": level, "title": "", "signature_ids": list(g.sig_ids),
                "categories": sorted(g.categories), "reasons": reasons,
                "ts_first": g.first_ts, "ts_last": g.last_ts, "t_first": g.first_t, "t_last": g.last_t,
                "count": g.count, "distinct_subjects": len(g.pids), "max_rssi": g.max_rssi,
                "zones": sorted(g.zones), "sensors": sorted(g.sensors),
                "event_refs": list(g.event_refs[:20]), "decisions": [],
            }
            self.clues[cid] = clue
            clue["title"] = self._title(clue)
            return dict(clue, _change="created")
        clue = self.clues[cid]
        before = clue["level"]
        # never downgrade automatically
        if LEVELS.index(level) > LEVELS.index(before):
            clue["level"] = level
        for r in reasons:
            kind = _reason_kind(r)
            idx = next((i for i, x in enumerate(clue["reasons"]) if kind and _reason_kind(x) == kind), None)
            if idx is not None:
                clue["reasons"][idx] = r          # refresh measured values in place
            elif r not in clue["reasons"]:
                clue["reasons"].append(r)
        clue.update(ts_last=g.last_ts, t_last=g.last_t, count=g.count, distinct_subjects=len(g.pids),
                    max_rssi=g.max_rssi, signature_ids=list(g.sig_ids), categories=sorted(g.categories),
                    zones=sorted(g.zones), sensors=sorted(g.sensors))
        if clue["level"] != before:
            return dict(clue, _change="level")
        return None

    def _combos(self, t: float) -> list[dict]:
        out = []
        glasses = [c for c in self.clues.values() if "smart_glasses" in c["categories"]]
        direct = [c for c in self.clues.values() if "wifi_direct" in c["categories"]]
        reason = "스마트안경 BLE 단서와 Wi-Fi Direct 그룹이 같은 시간대에 출현"
        for gc in glasses:
            if reason in gc["reasons"]:
                continue
            if gc["max_rssi"] is not None and gc["max_rssi"] < self.cfg.weak_rssi_dbm:
                continue  # corridor-strength signals are never escalated
            for dc in direct:
                if abs(dc["t_first"] - gc["t_last"]) <= self.cfg.combo_window_s or \
                   abs(gc["t_first"] - dc["t_last"]) <= self.cfg.combo_window_s:
                    gc["reasons"].append(reason)
                    if gc["level"] != "urgent":
                        gc["level"] = "urgent"
                        out.append(dict(gc, _change="level"))
                    break
        return out

    @staticmethod
    def _title(c: dict) -> str:
        cat = c["categories"][0] if c["categories"] else None
        names = {
            "smart_glasses": "스마트안경 신호 단서", "earbuds": "무선 이어버드 신호 단서",
            "phone_hotspot": "휴대폰 핫스팟 단서", "wifi_direct": "Wi-Fi Direct 그룹 단서",
            "hidden_camera": "카메라 기기 단서", "tracker": "트래커 단서", "radio_tx": "무선 송신기 단서",
        }
        if cat in names:
            return names[cat]
        return {
            "ble.adv": "새 BLE 신호", "wifi.beacon": "새 Wi-Fi 네트워크", "wifi.probe_req": "새 Wi-Fi 단말 탐색 신호",
            "wifi.station": "새 Wi-Fi 단말 활동", "wifi.p2p": "Wi-Fi Direct 활동", "rf.energy": "대역 에너지 증가",
            "detector.alert": "탐지기 경보 / 수동 입력", "ble.conn_activity": "BLE 연결 트래픽",
        }.get(c["kind"], "새 신호")

    def add_decision(self, clue_id: str, decision: dict) -> dict:
        clue = self.clues[clue_id]
        clue["decisions"].append(decision)
        return clue
