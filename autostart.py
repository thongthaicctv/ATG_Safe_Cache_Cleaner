import sys
from pathlib import Path

import winreg


APP_NAME = "ATG_SAFE_CACHE_CLEANER"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def get_entry_script_path():
    return Path(__file__).resolve().with_name("main.py")


def get_python_launcher():
    python_exe = Path(sys.executable).resolve()
    pythonw_exe = python_exe.with_name("pythonw.exe")

    if pythonw_exe.exists():
        return pythonw_exe

    return python_exe


def get_autostart_command():
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable).resolve()
        return f'"{exe_path}" --startup'

    launcher = get_python_launcher()
    script_path = get_entry_script_path()
    return f'"{launcher}" "{script_path}" --startup'


def get_registered_autostart_value():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_READ,
        )

        try:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return str(value).strip()
        finally:
            winreg.CloseKey(key)
    except FileNotFoundError:
        return ""


def enable_autostart():
    command = get_autostart_command()
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        RUN_KEY,
        0,
        winreg.KEY_SET_VALUE,
    )

    try:
        winreg.SetValueEx(
            key,
            APP_NAME,
            0,
            winreg.REG_SZ,
            command,
        )
    finally:
        winreg.CloseKey(key)


def disable_autostart():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        )

        try:
            winreg.DeleteValue(key, APP_NAME)
        finally:
            winreg.CloseKey(key)
    except FileNotFoundError:
        pass


def is_autostart_enabled():
    registered_value = get_registered_autostart_value()

    if not registered_value:
        return False

    return registered_value == get_autostart_command()
