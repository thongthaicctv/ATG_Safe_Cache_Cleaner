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


def get_machine_code():

    system = platform.system()
    node = platform.node()
    mac = hex(uuid.getnode())

    raw = f"{system}-{node}-{mac}-{APP_SECRET}"

    return hashlib.sha256(
        raw.encode()
    ).hexdigest()[:16].upper()


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