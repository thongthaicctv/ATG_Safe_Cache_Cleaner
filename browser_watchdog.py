import time

import psutil


BROWSER_PROCESSES = {
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "browser.exe": "Coc Coc / UC Browser",
    "firefox.exe": "Mozilla Firefox",
    "ucbrowser.exe": "UC Browser",
    "ucbrowsercore.exe": "UC Browser",
}

MEMORY_CACHE_TTL_SECONDS = 5.0

_browser_memory_cache = {}
_browser_memory_cache_timestamp = 0.0


def format_size(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def get_browser_memory(force_refresh=False):
    global _browser_memory_cache
    global _browser_memory_cache_timestamp

    now = time.monotonic()

    if (
        force_refresh
        or not _browser_memory_cache
        or now - _browser_memory_cache_timestamp >= MEMORY_CACHE_TTL_SECONDS
    ):
        result = {}

        for proc in psutil.process_iter(["name", "memory_info"]):
            try:
                name = proc.info["name"]

                if not name:
                    continue

                browser_name = BROWSER_PROCESSES.get(name.lower())

                if not browser_name:
                    continue

                memory = proc.info["memory_info"].rss

                if browser_name not in result:
                    result[browser_name] = {
                        "processes": 0,
                        "memory": 0,
                    }

                result[browser_name]["processes"] += 1
                result[browser_name]["memory"] += memory

            except Exception:
                pass

        _browser_memory_cache = result
        _browser_memory_cache_timestamp = now

    return _browser_memory_cache


def get_browser_memory_text():
    data = get_browser_memory()

    if not data:
        return "Khong phat hien trinh duyet dang chay."

    lines = []

    for browser, info in data.items():
        lines.append(
            f"{browser}: {info['processes']} process | RAM: {format_size(info['memory'])}"
        )

    return "\n".join(lines)


def is_browser_memory_high(limit_gb=4):
    data = get_browser_memory()
    limit_bytes = limit_gb * 1024 * 1024 * 1024

    for browser, info in data.items():
        if info["memory"] >= limit_bytes:
            return True, browser, info["memory"]

    return False, None, 0


if __name__ == "__main__":
    print(get_browser_memory_text())

    high, browser, memory = is_browser_memory_high(4)

    if high:
        print(f"Canh bao: {browser} dang dung RAM cao: {format_size(memory)}")
