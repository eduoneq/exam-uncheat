"""Privacy gate: pseudonymize device identifiers before anything is persisted.

Raw MAC/BLE addresses exist only in memory during ingest. They are replaced with
HMAC-SHA256(session_key, addr) truncated to 16 hex chars. The session key is
discarded when the session closes, so pseudonyms cannot be linked across sessions.
"""
from __future__ import annotations

import hashlib
import hmac
import os


def mask_text(s: str) -> str:
    if not s:
        return s
    if len(s) <= 3:
        return "*" * len(s)
    return f"{s[:2]}***({len(s)})"


class PrivacyGate:
    def __init__(self, key: bytes | None = None):
        self.key = key or os.urandom(32)

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.key).hexdigest()[:16]

    def pid(self, value: str) -> str:
        if self.key is None:
            raise RuntimeError("session key destroyed")
        return hmac.new(self.key, value.strip().lower().encode(), hashlib.sha256).hexdigest()[:16]

    def destroy(self) -> None:
        self.key = None  # type: ignore[assignment]

    def scrub(self, evt: dict) -> dict:
        """Return a copy safe to persist."""
        out = {k: v for k, v in evt.items() if k != "subject"}
        subj = evt.get("subject") or {}
        if subj:
            s = {}
            addr = subj.get("addr")
            if addr:
                s["pid"] = self.pid(addr)
                first = int(addr.split(":")[0], 16)
                locally_admin = bool(first & 0x02)
                if subj.get("addr_type") == "public" and not locally_admin:
                    s["oui"] = addr.upper()[:8]
            elif subj.get("pid"):
                s["pid"] = subj["pid"]
            if "addr_type" in subj:
                s["addr_type"] = subj["addr_type"]
            out["subject"] = s
        attrs = dict(evt.get("attrs") or {})
        for key in ("bssid", "go_bssid"):
            if key in attrs:
                attrs[f"{key}_pid"] = self.pid(str(attrs.pop(key)))
        for key in ("ssid", "name", "device_name"):
            if attrs.get(key):
                attrs[f"{key}_pid"] = self.pid("txt:" + attrs[key])
                attrs[key] = mask_text(attrs[key])
        out["attrs"] = attrs
        return out
