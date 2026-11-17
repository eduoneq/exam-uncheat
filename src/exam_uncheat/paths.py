"""Locate the repository data directories (spec/, signatures/)."""
from __future__ import annotations

import os
from pathlib import Path


def project_home() -> Path:
    env = os.environ.get("EXAM_UNCHEAT_HOME")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "spec" / "event.schema.json").exists():
            return parent
    raise FileNotFoundError("cannot locate spec/ — set EXAM_UNCHEAT_HOME to the repository root")


def spec_dir() -> Path:
    return project_home() / "spec"


def signatures_dir() -> Path:
    return project_home() / "signatures"
