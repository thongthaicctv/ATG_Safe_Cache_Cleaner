import os
from pathlib import Path

from safe_cleaner import get_target_folders, format_size

DANGER_CACHE_NAMES = {
    "GPUCache",
    "Code Cache",
}


def folder_size(path: Path):
    total_size = 0
    total_files = 0

    if not path.exists():
        return 0, 0

    try:
        for root, _, files in os.walk(path):
            for name in files:
                file_path = Path(root) / name

                try:
                    total_size += file_path.stat().st_size
                    total_files += 1
                except Exception:
                    pass
    except Exception:
        pass

    return total_size, total_files


def get_cache_metrics():
    items = []
    total_size = 0
    total_files = 0
    danger_size = 0
    danger_files = 0

    for folder in get_target_folders():
        size, files = folder_size(folder)

        items.append(
            {
                "path": str(folder),
                "name": folder.name,
                "size": size,
                "files": files,
            }
        )

        total_size += size
        total_files += files

        if folder.name in DANGER_CACHE_NAMES:
            danger_size += size
            danger_files += files

    items.sort(key=lambda item: item["size"], reverse=True)

    return {
        "items": items,
        "total_size": total_size,
        "total_files": total_files,
        "danger_size": danger_size,
        "danger_files": danger_files,
    }


def get_cache_status():
    return get_cache_metrics()["items"]


def get_total_cache_size():
    metrics = get_cache_metrics()
    return metrics["total_size"], metrics["total_files"]


def get_danger_cache_size():
    metrics = get_cache_metrics()
    return metrics["danger_size"], metrics["danger_files"]


def get_cache_status_text(limit=10):
    metrics = get_cache_metrics()
    items = metrics["items"]

    if not items:
        return "Khong tim thay cache an toan."

    lines = [
        f"Tong cache an toan: {format_size(metrics['total_size'])} | {metrics['total_files']} file"
    ]

    for item in items[:limit]:
        lines.append(
            f"{item['name']}: {format_size(item['size'])} | {item['files']} file"
        )

    return "\n".join(lines)


def is_cache_high(limit_gb=2):
    metrics = get_cache_metrics()
    limit_bytes = limit_gb * 1024 * 1024 * 1024

    return (
        metrics["total_size"] >= limit_bytes,
        metrics["total_size"],
        metrics["total_files"],
    )


def is_danger_cache_high(limit_gb=1):
    metrics = get_cache_metrics()
    limit_bytes = limit_gb * 1024 * 1024 * 1024

    return (
        metrics["danger_size"] >= limit_bytes,
        metrics["danger_size"],
        metrics["danger_files"],
    )


if __name__ == "__main__":
    print(get_cache_status_text())

    high, size, files = is_cache_high(2)

    if high:
        print(f"Canh bao tong cache cao: {format_size(size)} | {files} file")
    else:
        print(f"Tong cache binh thuong: {format_size(size)} | {files} file")

    danger_high, danger_size, danger_files = is_danger_cache_high(1)

    if danger_high:
        print(
            f"Canh bao GPUCache/Code Cache cao: "
            f"{format_size(danger_size)} | {danger_files} file"
        )
    else:
        print(
            f"GPUCache/Code Cache binh thuong: "
            f"{format_size(danger_size)} | {danger_files} file"
        )
