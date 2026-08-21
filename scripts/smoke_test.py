"""Run the deterministic inventory-to-production smoke proof."""
from __future__ import print_function

from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def main():
    command = [sys.executable, "-m", "pytest", "tests/e2e/test_seed_and_mock_smoke.py", "-q"]
    return subprocess.call(command, cwd=str(REPOSITORY_ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
