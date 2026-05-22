import time

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
        "name": "Coc Coc",
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
            "ucbrowsercore.exe",
        ],
    },
}

PROCESS_CACHE_TTL_SECONDS = 3.0

_process_snapshot = set()
_process_snapshot_timestamp = 0.0


def get_running_process_names(force_refresh=False):
    global _process_snapshot
    global _process_snapshot_timestamp

    now = time.monotonic()

    if (
        force_refresh
        or not _process_snapshot
        or now - _process_snapshot_timestamp >= PROCESS_CACHE_TTL_SECONDS
    ):
        names = set()

        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info.get("name", "")

                if name:
                    names.add(name.lower())

            except Exception:
                pass

        _process_snapshot = names
        _process_snapshot_timestamp = now

    return _process_snapshot


def is_process_running(process_names, process_snapshot=None):
    process_name_set = {
        process_name.lower()
        for process_name in process_names
    }

    if process_snapshot is None:
        process_snapshot = get_running_process_names()

    return any(
        process_name in process_snapshot
        for process_name in process_name_set
    )


def get_running_browsers(process_snapshot=None):
    if process_snapshot is None:
        process_snapshot = get_running_process_names()

    running = {}

    for key, info in BROWSERS.items():
        running[key] = {
            "name": info["name"],
            "running": is_process_running(
                info["processes"],
                process_snapshot=process_snapshot,
            ),
        }

    return running


def is_any_browser_running(process_snapshot=None):
    if process_snapshot is None:
        process_snapshot = get_running_process_names()

    return any(
        is_process_running(
            info["processes"],
            process_snapshot=process_snapshot,
        )
        for info in BROWSERS.values()
    )


def get_clean_mode(process_snapshot=None):
    """
    SAFE = browser dang mo, chi don cache an toan
    DEEP = browser da dong, co the don sau hon
    """

    if is_any_browser_running(process_snapshot=process_snapshot):
        return "SAFE"

    return "DEEP"


def browser_status_text():
    process_snapshot = get_running_process_names()
    browsers = get_running_browsers(process_snapshot=process_snapshot)
    lines = []

    for item in browsers.values():
        status = "Dang chay" if item["running"] else "Da tat"
        lines.append(f"{item['name']}: {status}")

    mode = get_clean_mode(process_snapshot=process_snapshot)
    lines.append(f"Che do don hien tai: {mode}")

    return "\n".join(lines)


if __name__ == "__main__":
    print(browser_status_text())
