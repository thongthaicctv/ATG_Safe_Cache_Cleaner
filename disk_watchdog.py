import shutil
from pathlib import Path


def get_free_gb(folder):
    try:
        drive = Path(folder).anchor
        total, used, free = shutil.disk_usage(drive)
        return free / (1024 ** 3)
    except Exception:
        return 0


def is_disk_low(folder, limit_gb=5):
    free_gb = get_free_gb(folder)
    return free_gb < limit_gb, free_gb