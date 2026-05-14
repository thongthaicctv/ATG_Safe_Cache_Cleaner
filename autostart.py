import sys
import winreg


APP_NAME = "ATG_SAFE_CACHE_CLEANER"


def get_exe_path():
    return sys.executable


def enable_autostart():

    exe_path = get_exe_path()

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE
    )

    winreg.SetValueEx(
        key,
        APP_NAME,
        0,
        winreg.REG_SZ,
        f'"{exe_path}"'
    )

    winreg.CloseKey(key)


def disable_autostart():

    try:

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )

        winreg.DeleteValue(
            key,
            APP_NAME
        )

        winreg.CloseKey(key)

    except FileNotFoundError:
        pass


def is_autostart_enabled():

    try:

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ
        )

        value, _ = winreg.QueryValueEx(
            key,
            APP_NAME
        )

        winreg.CloseKey(key)

        return bool(value)

    except FileNotFoundError:
        return False