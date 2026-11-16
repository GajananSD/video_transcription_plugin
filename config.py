"""Settings, read from .env / environment."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_env_file(path: Path) -> None:
    """Minimal .env reader (KEY=VALUE lines), so no extra package is needed."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_env_file(BASE_DIR / ".env")

PLUGIN_NAME = os.getenv("PLUGIN_NAME", "Conversation Insights")
TEAM_NAME = os.getenv("TEAM_NAME", "")             # shown next to the plugin in the app
HOST = os.getenv("PLUGIN_HOST", "0.0.0.0")        # 0.0.0.0 = reachable from other laptops
PORT = int(os.getenv("PLUGIN_PORT", "8300"))

# A word below this confidence counts as "unsure".
LOW_CONFIDENCE = float(os.getenv("LOW_CONFIDENCE", "0.30"))
# How many unsure words close together make a stretch worth re-listening.
UNSURE_MIN_WORDS = int(os.getenv("UNSURE_MIN_WORDS", "3"))
UNSURE_WINDOW_S = float(os.getenv("UNSURE_WINDOW_S", "5.0"))
# One speaker above this share of talk time gets an "attention" flag.
DOMINANCE_SHARE = float(os.getenv("DOMINANCE_SHARE", "0.70"))
# Chart bucket size in seconds.
WINDOW_S = float(os.getenv("WINDOW_S", "15"))
