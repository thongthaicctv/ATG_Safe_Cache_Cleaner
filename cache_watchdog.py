import os
from pathlib import Path

from safe_cleaner import get_target_folders, format_size

DANGER_CACHE_NAMES = [
    "GPUCache",
    "Code Cache",
]


def folder_size(path: Path):
    total_size = 0
    total_files = 0

    if not path.exists():
        return 0, 0

    try:
        for root, dirs, files in os.walk(path):
            for name in files:
                fp = Path(root) / name
                try:
                    total_size += fp.stat().st_size
                    total_files += 1
                except Exception:
                    pass
    except Exception:
        pass

    return total_size, total_files


def get_cache_status():
    result = []

    targets = get_target_folders()

    for folder in targets:
        size, files = folder_size(folder)

        result.append({
            "path": str(folder),
            "name": folder.name,
            "size": size,
            "files": files,
        })

    result.sort(key=lambda x: x["size"], reverse=True)

    return result


def get_total_cache_size():
    total_size = 0
    total_files = 0

    for item in get_cache_status():
        total_size += item["size"]
        total_files += item["files"]

    return total_size, total_files



def get_danger_cache_size():
    total_size = 0
    total_files = 0

    for item in get_cache_status():
        if item["name"] in DANGER_CACHE_NAMES:
            total_size += item["size"]
            total_files += item["files"]

    return total_size, total_files


def get_cache_status_text(limit=10):
    items = get_cache_status()

    if not items:
        return "Không tìm thấy cache an toàn."

    total_size, total_files = get_total_cache_size()

    lines = [
        f"Tổng cache an toàn: {format_size(total_size)} | {total_files} file"
    ]

    for item in items[:limit]:
        lines.append(
            f"{item['name']}: {format_size(item['size'])} | {item['files']} file"
        )

    return "\n".join(lines)


def is_cache_high(limit_gb=2):
    total_size, total_files = get_total_cache_size()
    limit_bytes = limit_gb * 1024 * 1024 * 1024

    return total_size >= limit_bytes, total_size, total_files


def is_danger_cache_high(limit_gb=1):
    size, files = get_danger_cache_size()

    limit_bytes = limit_gb * 1024 * 1024 * 1024

    return size >= limit_bytes, size, files



if __name__ == "__main__":
    print(get_cache_status_text())

    high, size, files = is_cache_high(2)

    if high:
        print(f"Cảnh báo tổng cache cao: {format_size(size)} | {files} file")
    else:
        print(f"Tổng cache bình thường: {format_size(size)} | {files} file")

    danger_high, danger_size, danger_files = is_danger_cache_high(1)

    if danger_high:
        print(
            f"Cảnh báo GPUCache/Code Cache cao: "
            f"{format_size(danger_size)} | {danger_files} file"
        )
    else:
        print(
            f"GPUCache/Code Cache bình thường: "
            f"{format_size(danger_size)} | {danger_files} file"
        )