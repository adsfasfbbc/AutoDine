from __future__ import annotations

import sys
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(MODULE_ROOT / "src"))

from smart_storage_vision.cli import main


if __name__ == "__main__":
    raise SystemExit(main())

