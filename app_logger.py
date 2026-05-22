from datetime import datetime
from pathlib import Path
import os
import time


APP_NAME = "ATG_SAFE_CACHE_CLEANER"
LOG_DEDUP_WINDOW_SECONDS = 30

_last_log_message = None
_last_log_timestamp = 0.0


def get_app_data_dir():
    base = os.getenv("LOCALAPPDATA")

    if base:
        path = Path(base) / APP_NAME
    else:
        path = Path.home() / APP_NAME

    path.mkdir(parents=True, exist_ok=True)
    return path


def write_log(message):
    global _last_log_message
    global _last_log_timestamp

    try:
        message = str(message).strip()

        if not message:
            return

        now_monotonic = time.monotonic()

        if (
            message == _last_log_message
            and now_monotonic - _last_log_timestamp < LOG_DEDUP_WINDOW_SECONDS
        ):
            return

        _last_log_message = message
        _last_log_timestamp = now_monotonic

        log_dir = get_app_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        current_time = datetime.now()
        today = current_time.strftime("%Y-%m-%d")
        now = current_time.strftime("%H:%M:%S")

        log_file = log_dir / f"log_{today}.txt"

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{now}] {message}\n")

    except Exception:
        pass
