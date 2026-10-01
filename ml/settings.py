import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = Path(os.environ.get("MODELS_DIR", REPO_ROOT / "ml" / "artifacts"))
if not MODELS_DIR.is_absolute():
    MODELS_DIR = REPO_ROOT / MODELS_DIR
