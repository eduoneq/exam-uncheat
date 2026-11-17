"""Scenario simulator: synthetic events in the exact on-wire format sensors emit.

All addresses are random *locally administered* MACs derived from a seed —
no real device identifiers appear in simulator output.

Timeline (seconds from scenario start):
  0–120    빈 교실 기준선: school AP beacons, classroom BLE device, weak hallway BLE
  120      control: start_exam
  180–320  smart glasses BLE adverts (address rotates at 260)
  330–420  Wi-Fi Direct group appears (glasses media transfer hypothesis)
  440–540  phone hotspot appears
  560–660  earbuds (Fast Pair + Apple proximity pairing)
  200–300  unknown new BLE device (no signature)
  680–710  weak Meta advert from corridor
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

SCENARIOS = ("baseline", "glasses", "hotspot", "earbuds", "all")
BASELINE_S = 120
END_S = 720


class _Gen:
    def __init__(self, seed: int, base: datetime, room: str):
        self.rng = random.Random(seed)
        self.base = base
        self.room = room
        self.items: list[dict] = []

    def mac(self) -> str:
        b = [self.rng.randrange(256) for _ in range(6)]
        b[0] = (b[0] & 0xFC) | 0x02  # locally administered, unicast
        return ":".join(f"{x:02x}" for x in b)

    def ev(self, t: float, sensor: str, zone: str, kind: str, **kw) -> None:
        e = {
            "schema": "exam-uncheat.event/v1",
            "offset_s": round(t, 3),
            "ts": (self.base + timedelta(seconds=t)).isoformat(timespec="milliseconds"),
            "sensor": {"id": sensor, "driver": "simulator@0.1.0",
                       "location": {"site": "demo-school", "room": self.room, "zone": zone}},
            "kind": kind,
        }
        e.update(kw)
        self.items.append(e)

    def jitter(self, base: float, spread: float = 4.0) -> float:
        return base + self.rng.uniform(-spread, spread)


def build(scenario: str = "all", seed: int = 7, base: datetime | None = None, room: str = "301") -> list[dict]:
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {scenario}; choose from {SCENARIOS}")
    base = base or datetime(2026, 11, 18, 9, 0, 0).astimezone()
    g = _Gen(seed, base, room)
    hello = [
        {"schema": "exam-uncheat.hello/v1", "sensor_id": "sim-ble-front", "driver": "simulator", "driver_version": "0.1.0",
         "hw": "simulated ESP32-S3", "capabilities": ["ble.adv"], "bands": ["2.4GHz"], "tx_capable": False, "offset_s": 0},
        {"schema": "exam-uncheat.hello/v1", "sensor_id": "sim-wifi-front", "driver": "simulator", "driver_version": "0.1.0",
         "hw": "simulated ESP32-C5", "capabilities": ["wifi.mgmt"], "bands": ["2.4GHz", "5GHz"], "tx_capable": False,
         "offset_s": 0},
    ]
    ap1, ap2 = g.mac(), g.mac()
    projector = g.mac()
    hallway = g.mac()

    # ---- background present for the whole session (part of baseline) ----
    t = 0.0
    while t < END_S:
        g.ev(t, "sim-wifi-front", "front", "wifi.beacon", band="2.4GHz", channel=1, rssi_dbm=-58 + g.rng.randint(-3, 3),
             subject={"addr": ap1, "addr_type": "public"}, attrs={"ssid": "SCHOOL-EDU", "bssid": ap1, "security": "wpa2"})
        g.ev(t + 0.5, "sim-wifi-front", "front", "wifi.beacon", band="5GHz", channel=36, rssi_dbm=-66 + g.rng.randint(-3, 3),
             subject={"addr": ap2, "addr_type": "public"}, attrs={"ssid": "SCHOOL-EDU", "bssid": ap2, "security": "wpa2"})
        g.ev(t + 1.0, "sim-ble-front", "front", "ble.adv", rssi_dbm=-62 + g.rng.randint(-4, 4),
             subject={"addr": projector, "addr_type": "random"}, attrs={"company_id": 0x0075, "connectable": False})
        g.ev(t + 2.0, "sim-ble-front", "front", "ble.adv", rssi_dbm=-93 + g.rng.randint(-3, 2),
             subject={"addr": hallway, "addr_type": "random"}, attrs={"company_id": 0x0006, "connectable": False})
        t += 5.0

    items_ctrl = [{"schema": "exam-uncheat.control/v1", "action": "start_exam", "offset_s": BASELINE_S}]

    want = (lambda name: scenario in (name, "all"))

    if want("glasses"):
        mac = g.mac()
        # "META_RB_GLASS" in manufacturer data after a 2-byte header (illustrative layout)
        mfg = "0100" + "META_RB_GLASS".encode().hex()
        t = 180.0
        while t < 320:
            if t >= 260 and t < 261:
                mac = g.mac()  # BLE address rotation
            g.ev(t, "sim-ble-front", "front", "ble.adv", rssi_dbm=-55 + g.rng.randint(-5, 5),
                 subject={"addr": mac, "addr_type": "random"},
                 attrs={"company_id": 0x01AB, "service_uuids": ["fd5f"], "mfg_data_hex": mfg,
                        "connectable": True, "phy": "1M"})
            t += 1.0
        p2p = g.mac()
        t = 330.0
        while t < 420:
            g.ev(t, "sim-wifi-front", "front", "wifi.beacon", band="2.4GHz", channel=6, rssi_dbm=-57 + g.rng.randint(-4, 4),
                 subject={"addr": p2p, "addr_type": "random"},
                 attrs={"ssid": "DIRECT-k3-Glasses", "bssid": p2p, "is_p2p_go": True, "security": "wpa2"})
            t += 2.0
        unk = g.mac()
        t = 200.0
        while t < 300:
            g.ev(t, "sim-ble-front", "front", "ble.adv", rssi_dbm=-75 + g.rng.randint(-4, 4),
                 subject={"addr": unk, "addr_type": "random"}, attrs={"company_id": 0x038F})
            t += 3.0
        weak = g.mac()
        t = 680.0
        while t < 712:
            g.ev(t, "sim-ble-front", "front", "ble.adv", rssi_dbm=-94 + g.rng.randint(-2, 2),
                 subject={"addr": weak, "addr_type": "random"}, attrs={"company_id": 0x01AB})
            t += 2.0

    if want("hotspot"):
        hs = g.mac()
        t = 440.0
        while t < 540:
            g.ev(t, "sim-wifi-front", "front", "wifi.beacon", band="2.4GHz", channel=11, rssi_dbm=-60 + g.rng.randint(-4, 4),
                 subject={"addr": hs, "addr_type": "random"},
                 attrs={"ssid": "OOO의 iPhone", "bssid": hs, "security": "wpa2"})
            t += 2.0
        sta = g.mac()
        t = 450.0
        while t < 540:
            g.ev(t, "sim-wifi-front", "front", "wifi.probe_req", band="2.4GHz", channel=11, rssi_dbm=-63,
                 subject={"addr": sta, "addr_type": "random"},
                 attrs={"ssid": "", "is_wildcard": True, "ie_fingerprint": "sim-fp-camera-01", "p2p_ie": False})
            t += 6.0

    if want("earbuds"):
        fp = g.mac()
        t = 560.0
        while t < 660:
            g.ev(t, "sim-ble-front", "front", "ble.adv", rssi_dbm=-64 + g.rng.randint(-4, 4),
                 subject={"addr": fp, "addr_type": "random"},
                 attrs={"service_data": {"fe2c": "aabbcc"}, "connectable": True})
            t += 1.5
        ap = g.mac()
        t = 580.0
        while t < 660:
            g.ev(t, "sim-ble-front", "front", "ble.adv", rssi_dbm=-66 + g.rng.randint(-4, 4),
                 subject={"addr": ap, "addr_type": "random"},
                 attrs={"company_id": 0x004C, "mfg_data_hex": "0719010e2055aa", "connectable": False})
            t += 1.5

    items = hello + items_ctrl + g.items
    items.sort(key=lambda o: o.get("offset_s", 0))
    return items


def write_jsonl(items: list[dict], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for o in items:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    return path
