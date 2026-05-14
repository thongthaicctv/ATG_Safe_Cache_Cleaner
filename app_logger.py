from datetime import datetime
from pathlib import Path


LOG_DIR = Path("logs")


def write_log(message):
    LOG_DIR.mkdir(exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M:%S")

    log_file = LOG_DIR / f"log_{today}.txt"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{now}] {message}\n")