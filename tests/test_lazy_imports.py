import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def test_main_import_does_not_import_httpx():
    code = (
        "import sys, os;"
        f"sys.path.insert(0, {str(SRC)!r});"
        "import main;"
        "raise SystemExit(1 if 'httpx' in sys.modules else 0)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
