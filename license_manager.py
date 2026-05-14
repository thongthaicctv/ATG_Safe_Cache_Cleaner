import csv
import hashlib
import io
import platform
import uuid
import requests

from datetime import datetime

APP_SECRET = "ATG_SAFE_CACHE_CLEANER"
SHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1WF0lRYnvs0MyduIy8TDqvcQ7G7hr38TBPZ_B-OTL1Uk"
    "/export?format=csv&gid=0"
)


def run_cmd(cmd):
    try:
        result = subprocess.check_output(
            cmd,
            shell=True,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            text=True
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


def get_machine_code():
    uuid_code = get_windows_uuid()
    bios_serial = get_bios_serial()
    computer_name = platform.node()

    raw = f"{uuid_code}|{bios_serial}|{computer_name}|{APP_SECRET}"

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16].upper()

def check_license():

    machine_code = get_machine_code()

    try:

        response = requests.get(
            SHEET_CSV_URL,
            timeout=10
        )

        csv_text = response.text

        reader = csv.DictReader(
            io.StringIO(csv_text)
        )

        for row in reader:

            sheet_machine = (
                row.get("MACHINE_CODE", "")
                .strip()
                .upper()
            )

            status = (
                row.get("STATUS", "")
                .strip()
                .upper()
            )

            expire_date = (
                row.get("EXPIRE_DATE", "")
                .strip()
            )

            customer = (
                row.get("CUSTOMER", "")
                .strip()
            )

            if sheet_machine != machine_code:
                continue

            if status != "ACTIVE":
                return (
                    False,
                    "License đã bị khóa"
                )

            if expire_date:

                expire = datetime.strptime(
                    expire_date,
                    "%Y-%m-%d"
                )

                if datetime.now() > expire:
                    return (
                        False,
                        "License đã hết hạn"
                    )

            return (
                True,
                f"{customer} | Hạn: {expire_date}"
            )

        return (
            False,
            "Không tìm thấy license"
        )

    except Exception as e:

        return (
            False,
            f"Lỗi license: {e}"
        )