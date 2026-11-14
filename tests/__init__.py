import sys
from pathlib import Path

# Let `python -m unittest` and pytest import the package straight from src/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
