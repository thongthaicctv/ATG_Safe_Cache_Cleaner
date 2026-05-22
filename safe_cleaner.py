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

TARGET_DISCOVERY_TTL_SECONDS = 10 * 60

_TARGET_FOLDER_LOOKUP = {
    name.lower(): name
    for name in SAFE_FOLDERS + DEEP_FOLDERS
}
_BLOCK_FOLDER_NAMES = {
    name.lower()
    for name in BLOCK_FOLDERS
}

_target_cache_timestamp = 0.0
_target_cache = {}


def expand_path(path):
    return Path(os.path.expandvars(path))


def is_block_folder(path):
    name = path.name.lower()

    for item in BLOCK_FOLDERS:
        if item.lower() == name:
            return True

    return False


def _discover_target_folders():
    discovered = {
        name: set()
        for name in SAFE_FOLDERS + DEEP_FOLDERS
    }

    for root in BROWSER_CACHE_DIRS:
        root_path = expand_path(root)

        try:
            root_exists = root_path.exists()
        except Exception:
            continue

        if not root_exists:
            continue

        try:
            for current_root, dir_names, _ in os.walk(root_path):
                current_path = Path(current_root)
                next_dir_names = []

                for dir_name in dir_names:
                    dir_name_lower = dir_name.lower()

                    target_name = _TARGET_FOLDER_LOOKUP.get(dir_name_lower)

                    if target_name:
                        discovered[target_name].add(current_path / dir_name)
                        continue

                    if dir_name_lower in _BLOCK_FOLDER_NAMES:
                        continue

                    next_dir_names.append(dir_name)

                # Do not descend into blocked folders or known cache folders.
                dir_names[:] = next_dir_names

        except Exception:
            pass

    return {
        name: tuple(sorted(paths))
        for name, paths in discovered.items()
        if paths
    }


def get_target_folders(mode=None, force_refresh=False):
    global _target_cache
    global _target_cache_timestamp

    if mode is None:
        mode = get_clean_mode()

    now = time.monotonic()

    if (
        force_refresh
        or not _target_cache
        or now - _target_cache_timestamp >= TARGET_DISCOVERY_TTL_SECONDS
    ):
        _target_cache = _discover_target_folders()
        _target_cache_timestamp = now

    folders = SAFE_FOLDERS.copy()

    if mode == "DEEP":
        folders += DEEP_FOLDERS

    targets = []

    for folder_name in folders:
        targets.extend(_target_cache.get(folder_name, ()))

    return targets


def iter_old_files(path, keep_days=7):
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
                    stats = fp.stat()

                    if delete_all or stats.st_mtime < cutoff:
                        yield fp, stats.st_size

                except Exception:
                    pass

    except Exception:
        pass


def get_old_files(path, keep_days=7):
    return [
        file_path
        for file_path, _ in iter_old_files(path, keep_days)
    ]


def clean_cache(
    keep_days=7,
    log_callback=None
):
    mode = get_clean_mode()
    targets = get_target_folders(mode=mode)

    deleted_files = 0
    deleted_size = 0
    skipped = 0

    for folder in targets:

        try:
            for file, size in iter_old_files(folder, keep_days):

                try:
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
    mode = get_clean_mode()
    targets = get_target_folders(mode=mode)

    total_size = 0
    total_files = 0

    for folder in targets:
        for _, size in iter_old_files(folder, keep_days):
            total_size += size
            total_files += 1

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
