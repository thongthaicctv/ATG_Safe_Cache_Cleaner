import os
import time
from pathlib import Path
from send2trash import send2trash


def iter_old_files(folder, keep_days=60):
    folder = Path(folder)

    if not folder.exists():
        return

    cutoff = time.time() - keep_days * 86400

    for root, _, files in os.walk(folder):
        for file_name in files:
            file_path = Path(root) / file_name

            try:
                stats = file_path.stat()

                if stats.st_mtime < cutoff:
                    yield file_path, stats.st_size

            except Exception:
                pass


def summarize_old_files(folder, keep_days=60):
    total_files = 0
    total_size = 0

    for _, size in iter_old_files(folder, keep_days):
        total_files += 1
        total_size += size

    return total_files, total_size


def find_old_files(folder, keep_days=60):
    old_files = []
    total_size = 0

    for file_path, size in iter_old_files(folder, keep_days):
        old_files.append(file_path)
        total_size += size

    return old_files, total_size


def clean_old_files(
    folder,
    keep_days=60,
    recycle_bin=True,
    log_callback=None
):
    deleted_files = 0
    deleted_size = 0
    skipped = 0

    for file, size in iter_old_files(folder, keep_days):

        try:
            if recycle_bin:
                send2trash(str(file))
            else:
                file.unlink()

            deleted_files += 1
            deleted_size += size

        except Exception:
            skipped += 1

    if log_callback:

        log_callback(
            f"Đã dọn file cũ: "
            f"{deleted_files} file | "
            f"{format_size(deleted_size)} | "
            f"Bỏ qua: {skipped}"
        )

    return (
        deleted_size,
        deleted_files,
        skipped
    )


def format_size(size):

    for unit in [
        "B",
        "KB",
        "MB",
        "GB",
        "TB"
    ]:

        if size < 1024:
            return f"{size:.2f} {unit}"

        size /= 1024

    return f"{size:.2f} PB"
