import psutil


BROWSER_PROCESSES = {
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "browser.exe": "Cốc Cốc / UC Browser",
    "firefox.exe": "Mozilla Firefox",
}


def format_size(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def get_browser_memory():
    result = {}

    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            name = proc.info["name"]

            if not name:
                continue

            name_lower = name.lower()

            if name_lower not in BROWSER_PROCESSES:
                continue

            browser_name = BROWSER_PROCESSES[name_lower]
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

    return result


def get_browser_memory_text():
    data = get_browser_memory()

    if not data:
        return "Không phát hiện trình duyệt đang chạy."

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
        print(f"Cảnh báo: {browser} đang dùng RAM cao: {format_size(memory)}")