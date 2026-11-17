#!/usr/bin/env python3
"""Rename the project in one step.

    python tools/rename.py NEW-NAME            # e.g. my-hub
    python tools/rename.py NEW-NAME --dry-run

The current name is read from PROJECT_NAME. Three spellings are replaced:
  distribution / CLI / display name   exam-uncheat   -> NEW-NAME
  Python package / import name        exam_uncheat   -> NEW_NAME
  environment-variable prefix         EXAM_UNCHEAT   -> NEW_NAME (upper case)
and src/<old_package> is renamed to src/<new_package>.
NEW-NAME must be lowercase letters, digits and hyphens, starting with a letter.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_EXT = {".py", ".md", ".toml", ".yml", ".yaml", ".json", ".html", ".txt", ".c", ".h", ".jsonl", ".ini", ".cfg", ".projbuild", ".defaults", ""}
SKIP = {".git", ".venv", "data", "__pycache__", "build", ".pio"}


def forms(name: str) -> tuple[str, str, str]:
    pkg = name.replace("-", "_")
    return name, pkg, pkg.upper()


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if len(args) != 1 or not re.fullmatch(r"[a-z][a-z0-9-]*[a-z0-9]", args[0]):
        sys.exit(__doc__)
    old = (ROOT / "PROJECT_NAME").read_text().strip()
    o_dist, o_pkg, o_env = forms(old)
    n_dist, n_pkg, n_env = forms(args[0])
    pairs = [(o_env, n_env), (o_pkg, n_pkg), (o_dist, n_dist)]
    changed = 0
    for p in ROOT.rglob("*"):
        if not p.is_file() or SKIP & set(p.parts) or p.suffix not in TEXT_EXT or p.name.startswith("LICENSE"):
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        new = text
        for a, b in pairs:
            new = new.replace(a, b)
        if new != text:
            changed += 1
            print("edit", p.relative_to(ROOT))
            if not dry:
                p.write_text(new, encoding="utf-8")
    src = ROOT / "src" / o_pkg
    if src.exists():
        print("move", f"src/{o_pkg}", "->", f"src/{n_pkg}")
        if not dry:
            src.rename(ROOT / "src" / n_pkg)
    print(f"{changed} files {'would change' if dry else 'changed'}; then run: pip install -e .")


if __name__ == "__main__":
    main()
