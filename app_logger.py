from datetime import datetime
from pathlib import Path
import os


APP_NAME = "ATG_SAFE_CACHE_CLEANER"


def get_app_data_dir():
    base = os.getenv("LOCALAPPDATA")

    if base:
        path = Path(base) / APP_NAME
    else:
        path = Path.home() / APP_NAME

    path.mkdir(parents=True, exist_ok=True)
    return path


def write_log(message):
    try:
        log_dir = get_app_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        now = datetime.now().strftime("%H:%M:%S")

        log_file = log_dir / f"log_{today}.txt"

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{now}] {message}\n")

    except Exception:
        pass