import sys
from pathlib import Path

# Make the src/ layout importable when running pytest from edge/front_vision/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
