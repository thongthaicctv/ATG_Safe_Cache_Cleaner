import psutil


BROWSERS = {
    "chrome": {
        "name": "Google Chrome",
        "processes": ["chrome.exe"],
    },

    "edge": {
        "name": "Microsoft Edge",
        "processes": ["msedge.exe"],
    },

    "coccoc": {
        "name": "Cốc Cốc",
        "processes": ["browser.exe"],
    },

    "firefox": {
        "name": "Mozilla Firefox",
        "processes": ["firefox.exe"],
    },

    "ucbrowser": {
        "name": "UC Browser",
        "processes": [
            "ucbrowser.exe",
            "ucbrowsercore.exe"
        ],
    },
}


def is_process_running(process_names):
    process_names = [p.lower() for p in process_names]

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = proc.info.get("name", "").lower()

            if name in process_names:
                return True

        except Exception:
            pass

    return False


def get_running_browsers():
    running = {}

    for key, info in BROWSERS.items():
        running[key] = {
            "name": info["name"],
            "running": is_process_running(info["processes"]),
        }

    return running


def is_any_browser_running():
    browsers = get_running_browsers()

    for item in browsers.values():
        if item["running"]:
            return True

    return False


def get_clean_mode():
    """
    SAFE = trình duyệt đang mở, chỉ dọn cache an toàn
    DEEP = trình duyệt đã đóng, có thể dọn sâu hơn
    """

    if is_any_browser_running():
        return "SAFE"

    return "DEEP"


def browser_status_text():
    browsers = get_running_browsers()
    lines = []

    for item in browsers.values():
        status = "Đang chạy" if item["running"] else "Đã tắt"
        lines.append(f"{item['name']}: {status}")

    mode = get_clean_mode()
    lines.append(f"Chế độ dọn hiện tại: {mode}")

    return "\n".join(lines)


if __name__ == "__main__":
    print(browser_status_text())