import time
from pathlib import Path
from send2trash import send2trash


def find_old_files(folder, keep_days=60):

    folder = Path(folder)

    if not folder.exists():
        return [], 0

    cutoff = time.time() - keep_days * 86400

    old_files = []
    total_size = 0

    for file in folder.rglob("*"):

        if not file.is_file():
            continue

        try:

            mtime = file.stat().st_mtime

            if mtime < cutoff:

                size = file.stat().st_size

                old_files.append(file)

                total_size += size

        except Exception:
            pass

    return old_files, total_size


def clean_old_files(
    folder,
    keep_days=60,
    recycle_bin=True,
    log_callback=None
):

    old_files, total_size = find_old_files(
        folder,
        keep_days
    )

    deleted_files = 0
    deleted_size = 0
    skipped = 0

    for file in old_files:

        try:

            size = file.stat().st_size

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