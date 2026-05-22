import csv
import hashlib
import io
import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import requests


APP_SECRET = "ATG_SAFE_CACHE_CLEANER"
APP_NAME = "ATG_SAFE_CACHE_CLEANER"
OFFLINE_GRACE_DAYS = 7
SHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1WF0lRYnvs0MyduIy8TDqvcQ7G7hr38TBPZ_B-OTL1Uk"
    "/export?format=csv&gid=0"
)


def get_app_data_dir():
    base = os.getenv("LOCALAPPDATA")

    if base:
        path = Path(base) / APP_NAME
    else:
        path = Path.home() / APP_NAME

    path.mkdir(parents=True, exist_ok=True)
    return path


def get_license_cache_file():
    return get_app_data_dir() / "license_cache.json"


def run_cmd(cmd):
    try:
        result = subprocess.check_output(
            cmd,
            shell=True,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            text=True,
        )
        return result.strip()
    except Exception:
        return ""


def get_windows_uuid():
    output = run_cmd("wmic csproduct get uuid")

    lines = [
        line.strip()
        for line in output.splitlines()
        if line.strip() and "UUID" not in line.upper()
    ]

    if lines:
        return lines[0]

    return ""


def get_bios_serial():
    output = run_cmd("wmic bios get serialnumber")

    lines = [
        line.strip()
        for line in output.splitlines()
        if line.strip() and "SERIAL" not in line.upper()
    ]

    if lines:
        return lines[0]

    return ""


def get_disk_serial():
    output = run_cmd("wmic diskdrive get serialnumber")

    lines = [
        line.strip()
        for line in output.splitlines()
        if line.strip() and "SERIAL" not in line.upper()
    ]

    return lines[0] if lines else ""


def get_machine_code():
    uuid_code = get_windows_uuid()
    bios_serial = get_bios_serial()
    disk_serial = get_disk_serial()

    raw = f"{uuid_code}|{bios_serial}|{disk_serial}|{APP_SECRET}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16].upper()


def clear_license_cache():
    cache_file = get_license_cache_file()

    try:
        cache_file.unlink(missing_ok=True)
    except Exception:
        pass


def save_license_cache(machine_code, customer, expire_date):
    cache_file = get_license_cache_file()
    data = {
        "machine_code": machine_code,
        "customer": customer,
        "expire_date": expire_date,
        "last_verified_at": datetime.now().isoformat(timespec="seconds"),
    }

    try:
        with open(cache_file, "w", encoding="utf-8") as file_obj:
            json.dump(data, file_obj, indent=4, ensure_ascii=False)
    except Exception:
        pass


def load_license_cache():
    cache_file = get_license_cache_file()

    try:
        with open(cache_file, "r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)

        if isinstance(data, dict):
            return data
    except Exception:
        return None

    return None


def parse_expire_date(expire_date):
    if not expire_date:
        return None

    return datetime.strptime(expire_date, "%Y-%m-%d")


def is_cached_license_valid(cache_data, machine_code):
    if not cache_data:
        return False, "Khong co cache license"

    if cache_data.get("machine_code", "").strip().upper() != machine_code:
        return False, "Cache license khong khop may"

    last_verified_at = cache_data.get("last_verified_at", "").strip()

    if not last_verified_at:
        return False, "Cache license thieu moc xac thuc"

    try:
        last_verified = datetime.fromisoformat(last_verified_at)
    except ValueError:
        return False, "Cache license khong hop le"

    if datetime.now() - last_verified > timedelta(days=OFFLINE_GRACE_DAYS):
        return False, "Cache license da het thoi gian offline"

    expire_date = cache_data.get("expire_date", "").strip()

    if expire_date:
        expire = parse_expire_date(expire_date)

        if datetime.now().date() > expire.date():
            return False, "License da het han"

    customer = cache_data.get("customer", "").strip()
    return True, f"{customer} | Han: {expire_date} | Offline cache"


def check_license():
    machine_code = get_machine_code()

    try:
        response = requests.get(SHEET_CSV_URL, timeout=10)
        response.raise_for_status()

        csv_text = response.text
        reader = csv.DictReader(io.StringIO(csv_text))

        for row in reader:
            sheet_machine = row.get("MACHINE_CODE", "").strip().upper()
            status = row.get("STATUS", "").strip().upper()
            expire_date = row.get("EXPIRE_DATE", "").strip()
            customer = row.get("CUSTOMER", "").strip()

            if sheet_machine != machine_code:
                continue

            if status != "ACTIVE":
                clear_license_cache()
                return False, "License da bi khoa"

            if expire_date:
                expire = parse_expire_date(expire_date)

                if datetime.now().date() > expire.date():
                    clear_license_cache()
                    return False, "License da het han"

            save_license_cache(machine_code, customer, expire_date)
            return True, f"{customer} | Han: {expire_date}"

        clear_license_cache()
        return False, "Khong tim thay license"

    except Exception as exc:
        cache_data = load_license_cache()
        cache_ok, cache_message = is_cached_license_valid(cache_data, machine_code)

        if cache_ok:
            return True, cache_message

        return False, f"Loi license: {exc}"
