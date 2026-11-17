#!/usr/bin/env python3
"""No-TX policy check (CI gate).

Fails if source code in the repository contains transmit, injection,
deauthentication, jamming or active-scan constructs. Documentation (*.md)
may *discuss* these topics; code may not *use* them.

Usage: python tools/no_tx_check.py [ROOT]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

CODE_EXT = {".py", ".c", ".h", ".cc", ".cpp", ".hpp", ".ino", ".js", ".ts", ".sh", ".rs", ".go", ".kt", ".java"}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "build", "dist", "__pycache__", "data"}
SELF = Path(__file__).resolve()

RULES: list[tuple[str, str]] = [
    # ESP-IDF / ESP32 transmit & active scanning
    (r"\besp_wifi_80211_tx\b", "raw 802.11 frame transmit"),
    (r"\besp_wifi_scan_start\b", "active Wi-Fi scan (sends probe requests)"),
    (r"\bsend_raw_frame\b", "raw frame transmit"),
    (r"\besp_ble_gap_start_advertising\b|\bble_gap_adv_start\b|\besp_ble_gap_config_adv_data\b", "BLE advertising (transmit)"),
    (r"\bble_gap_connect\b|\besp_ble_gattc_open\b|\bconnectGatt\b", "BLE connection attempt"),
    (r"\.passive\s*=\s*0\b", "BLE active scan (sends SCAN_REQ)"),
    (r"BLE_SCAN_TYPE_ACTIVE|SCAN_MODE_ACTIVE|scan_type\s*=\s*1\b", "BLE active scan"),
    (r"\bset_active_scan\s*\(\s*true", "BLE active scan"),
    # host-side injection / attack tooling
    (r"\b(aireplay-ng|aireplay|mdk3|mdk4|wifite|bettercap|airbase-ng)\b", "attack tooling"),
    (r"\b(sendp|srp1?|sr1)\s*\(", "scapy packet transmit"),
    (r"\bDot11Deauth\b|\bdeauth(entication)?_?(attack|frame|packet|send)\b", "deauthentication"),
    (r"\bhackrf_transfer\b[^\n]*\s-t\b|\bhackrf_start_tx\b|\bTX_VGA\b", "SDR transmit"),
    (r"(jam|jammer|jamming)\w*\s*\(", "jamming routine"),
    (r"\bhcitool\s+cmd\b|\bbtmgmt\s+advertising\b", "raw HCI / advertising"),
]


def scan(root: Path) -> list[str]:
    hits = []
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix not in CODE_EXT:
            continue
        if any(part in SKIP_DIRS for part in p.parts) or p.resolve() == SELF:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for rx, why in RULES:
                if re.search(rx, line, flags=re.IGNORECASE):
                    hits.append(f"{p.relative_to(root)}:{i}: {why}: {line.strip()[:120]}")
    return hits


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[1]
    hits = scan(root)
    if hits:
        print("No-TX policy violation(s): this project is receive-only.\n")
        print("\n".join(hits))
        print("\nSee CONTRIBUTING.md#no-tx-policy")
        return 1
    print("no-tx-check: OK (no transmit/injection/jamming/active-scan constructs found)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
