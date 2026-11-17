#!/usr/bin/env python3
"""Fail if sample/scenario JSONL contains a globally unique (vendor-assigned) MAC
other than documentation-safe test addresses. Simulator output uses only
locally administered addresses; real recordings must be scrubbed before commit."""
import json
import re
import sys
from pathlib import Path

MAC = re.compile(r"\b([0-9a-fA-F]{2})(:[0-9a-fA-F]{2}){5}\b")
bad = []
for p in Path(sys.argv[1] if len(sys.argv) > 1 else "scenarios").rglob("*.jsonl"):
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        for m in MAC.finditer(line):
            if not int(m.group(1), 16) & 0x02:
                bad.append(f"{p}:{i}: {m.group(0)}")
if bad:
    print("Globally unique MAC addresses found in samples (scrub real recordings first):")
    print("\n".join(bad[:50]))
    sys.exit(1)
print("check_samples: OK (only locally administered addresses)")
