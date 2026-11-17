import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "no_tx_check.py"


def test_repository_is_clean():
    r = subprocess.run([sys.executable, str(TOOL), str(ROOT)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


def test_checker_rejects_transmit_code(tmp_path):
    # Bad samples live in a JSON fixture so this test file itself stays clean.
    samples = json.loads((ROOT / "tests" / "fixtures" / "no_tx_samples.json").read_text())
    for name, code in samples.items():
        d = tmp_path / name.split(".")[0]
        d.mkdir()
        (d / name).write_text(code)
        r = subprocess.run([sys.executable, str(TOOL), str(d)], capture_output=True, text=True)
        assert r.returncode == 1, f"{name} not flagged: {r.stdout}"


def test_markdown_docs_may_discuss_countermeasures(tmp_path):
    (tmp_path / "LEGAL.md").write_text("재밍(jamming)은 구현하지 않는다. deauth 없음.")
    r = subprocess.run([sys.executable, str(TOOL), str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 0
