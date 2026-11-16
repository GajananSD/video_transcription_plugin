import sys
from pathlib import Path

# Make the plugin's modules (app, analysis, card, ...) importable from the tests.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
