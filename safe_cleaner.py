import os
import time
from pathlib import Path

from browser_detector import get_clean_mode


# =========================
# CACHE ROOT
# =========================

BROWSER_CACHE_DIRS = [

    # Chrome
    r"%LOCALAPPDATA%\Google\Chrome\User Data",

    # Edge
    r"%LOCALAPPDATA%\Microsoft\Edge\User Data",

    # CocCoc
    r"%LOCALAPPDATA%\CocCoc\Browser\User Data",

    # UC Browser
    r"%LOCALAPPDATA%\UCBrowser\User Data",

    # Firefox
    r"%LOCALAPPDATA%\Mozilla\Firefox\Profiles",
]


# =========================
# SAFE CLEAN
# =========================

SAFE_FOLDERS = [

    "GPUCache",
    "Code Cache",
    "ShaderCache",
    "GrShaderCache",
    "DawnCache",
    "Crashpad",
]


# =========================
# DEEP CLEAN
# =========================

DEEP_FOLDERS = [

    "Cache",
    "Media Cache",
]


# =========================
# NEVER TOUCH
# =========================

BLOCK_FOLDERS = [

    "Local Storage",
    "Session Storage",
    "Sessions",
    "IndexedDB",
    "Cookies",
    "Login Data",
    "History",
    "Web Data",
]


def expand_path(path):
    return Path(os.path.expandvars(path))


def is_block_folder(path):
    name = path.name.lower()

    for item in BLOCK_FOLDERS:
        if item.lower() == name:
            return True

    return False


def get_target_folders():

    mode = get_clean_mode()

    targets = []

    folders = SAFE_FOLDERS.copy()

    if mode == "DEEP":
        folders += DEEP_FOLDERS

    for root in BROWSER_CACHE_DIRS:

        root_path = expand_path(root)

        if not root_path.exists():
            continue

        try:
            for folder_name in folders:

                for found in root_path.rglob("*"):

                    if found.name != folder_name:
                        continue

                    if is_block_folder(found):
                        continue

                    targets.append(found)

        except Exception:
            pass

    return list(set(targets))


def get_old_files(path, keep_days=7):
    result = []

    delete_all = keep_days <= 0

    if not delete_all:
        cutoff = time.time() - keep_days * 86400
    else:
        cutoff = None

    try:
        for root, dirs, files in os.walk(path):
            for file in files:
                fp = Path(root) / file

                try:
                    if delete_all:
                        result.append(fp)
                    else:
                        mtime = fp.stat().st_mtime

                        if mtime < cutoff:
                            result.append(fp)

                except Exception:
                    pass

    except Exception:
        pass

    return result


def clean_cache(
    keep_days=7,
    log_callback=None
):

    mode = get_clean_mode()

    targets = get_target_folders()



    deleted_files = 0
    deleted_size = 0
    skipped = 0

    for folder in targets:

        try:

            old_files = get_old_files(
                folder,
                keep_days
            )

            for file in old_files:

                try:

                    size = file.stat().st_size

                    file.unlink()

                    deleted_files += 1
                    deleted_size += size

                except Exception:
                    skipped += 1

        except Exception:
            pass

    if log_callback:

        log_callback(
            f"[{mode}] "
            f"Đã dọn: "
            f"{deleted_files} file | "
            f"{format_size(deleted_size)} | "
            f"Bỏ qua: {skipped}"
        )

    return (
        deleted_size,
        deleted_files,
        skipped,
        mode
    )


def scan_cache(keep_days=7):

    targets = get_target_folders()

    total_size = 0
    total_files = 0

    for folder in targets:

        old_files = get_old_files(
            folder,
            keep_days
        )

        for file in old_files:

            try:

                total_size += file.stat().st_size
                total_files += 1

            except Exception:
                pass

    return (
        targets,
        total_size,
        total_files
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




if __name__ == "__main__":

    size, files, skipped, mode = clean_cache(
        keep_days=7,
        log_callback=print
    )

    print(mode)