import psutil

psutil.cpu_percent(interval=None)


def get_cpu_percent():
    return psutil.cpu_percent(interval=None)


def get_ram_percent():
    return psutil.virtual_memory().percent


def is_system_busy(cpu_limit=85, ram_limit=90):
    cpu = get_cpu_percent()
    ram = get_ram_percent()

    if cpu >= cpu_limit:
        return True, f"CPU cao: {cpu:.1f}%"

    if ram >= ram_limit:
        return True, f"RAM hệ thống cao: {ram:.1f}%"

    return False, f"CPU {cpu:.1f}% | RAM {ram:.1f}%"


if __name__ == "__main__":
    busy, msg = is_system_busy()
    print(msg)
