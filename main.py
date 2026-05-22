import json
import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QCursor, QIcon, QPixmap
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from app_logger import write_log
from autostart import disable_autostart, enable_autostart, is_autostart_enabled
from browser_detector import browser_status_text, get_clean_mode
from browser_watchdog import format_size as format_ram
from browser_watchdog import get_browser_memory_text, is_browser_memory_high
from cache_watchdog import get_cache_metrics
from disk_watchdog import is_disk_low
from file_cleaner import clean_old_files, summarize_old_files
from license_manager import check_license
from license_ui import LicenseDialog
from safe_cleaner import clean_cache, format_size, scan_cache
from system_watchdog import is_system_busy


APP_NAME = "ATG_SAFE_CACHE_CLEANER"
ICON_FILE = "assets/icon.ico"
LOGO_FILE = "assets/logo.png"
DISK_LOW_SOUND = "assets/disk_low.wav"

WATCHDOG_INTERVAL_MS = 30 * 1000
DISK_CHECK_INTERVAL_MS = 60 * 1000
CONFIG_SAVE_DEBOUNCE_MS = 600
WATCHDOG_CLEAN_COOLDOWN_SECONDS = 10 * 60
DISK_ALERT_COOLDOWN_SECONDS = 30 * 60
WATCHDOG_DANGER_CACHE_LIMIT_BYTES = 1 * 1024 * 1024 * 1024
WATCHDOG_BROWSER_RAM_LIMIT_GB = 6


def get_app_data_dir():
    base = os.getenv("LOCALAPPDATA")

    if base:
        path = Path(base) / APP_NAME
    else:
        path = Path.home() / APP_NAME

    path.mkdir(parents=True, exist_ok=True)
    return path


CONFIG_FILE = get_app_data_dir() / "config.json"


def resource_path(relative_path: str) -> str:
    base_path = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return str(Path(base_path) / relative_path)


def is_windows_startup():
    args = {arg.lower() for arg in sys.argv}
    return bool(args.intersection({"--startup", "/startup", "-startup"}))


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.is_quitting = False
        self.allow_close_to_tray = True
        self.last_watchdog_clean = 0.0
        self.cleaning_in_progress = False
        self.loading_ui = False
        self.last_disk_alert_at = {}

        self.setWindowTitle("V1.0.0 | ATG Safe Browser Cache Cleaner")
        self.resize(860, 720)
        self.setMinimumSize(760, 560)

        icon_path = resource_path(ICON_FILE)
        if Path(icon_path).exists():
            self.setWindowIcon(QIcon(icon_path))

        self.config = self.load_config()
        self.disk_low_sound = self.build_disk_low_sound()

        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self.auto_clean_task)

        self.watchdog_timer = QTimer(self)
        self.watchdog_timer.timeout.connect(self.watchdog_check)

        self.disk_timer = QTimer(self)
        self.disk_timer.timeout.connect(self.check_disk_space)

        self.config_save_timer = QTimer(self)
        self.config_save_timer.setSingleShot(True)
        self.config_save_timer.timeout.connect(self.save_config)

        self.init_ui()

        self.loading_ui = True
        self.load_ui_state()
        self.loading_ui = False

        self.refresh_browser_status()
        self.setup_tray()

        self.disk_timer.start(DISK_CHECK_INTERVAL_MS)
        QTimer.singleShot(10 * 1000, self.start_watchdog)

    def build_disk_low_sound(self):
        try:
            sound = QSoundEffect(self)
            sound_path = resource_path(DISK_LOW_SOUND)

            if Path(sound_path).exists():
                sound.setSource(QUrl.fromLocalFile(str(Path(sound_path).resolve())))
                sound.setVolume(0.9)

            return sound
        except Exception:
            return None

    def init_ui(self):
        root_layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root_layout.addWidget(scroll)

        content = QWidget()
        main_layout = QVBoxLayout(content)
        scroll.setWidget(content)

        header = QHBoxLayout()

        logo = QLabel()
        logo_path = resource_path(LOGO_FILE)

        if Path(logo_path).exists():
            pixmap = QPixmap(logo_path).scaled(
                54,
                54,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            logo.setPixmap(pixmap)

        header.addWidget(logo)

        title = QLabel("ATG Safe Browser Cache Cleaner")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size: 24px; font-weight: bold; color: #0B5ED7;"
        )
        header.addWidget(title, 1)

        main_layout.addLayout(header)

        status_group = QGroupBox("Trang thai trinh duyet")
        status_layout = QVBoxLayout(status_group)

        self.watchdog_info = QLabel("Watchdog: dang theo doi...")
        self.watchdog_info.setStyleSheet("font-size: 13px; color: #198754;")
        status_layout.addWidget(self.watchdog_info)

        self.browser_memory = QLabel("RAM trinh duyet: dang kiem tra...")
        self.browser_memory.setStyleSheet("font-size: 13px; color: #0B5ED7;")
        status_layout.addWidget(self.browser_memory)

        self.browser_status = QLabel("Dang kiem tra...")
        self.browser_status.setStyleSheet("font-size: 14px;")
        status_layout.addWidget(self.browser_status)

        self.btn_refresh_status = QPushButton("Kiem tra trang thai trinh duyet")
        self.btn_refresh_status.clicked.connect(self.refresh_browser_status)
        status_layout.addWidget(self.btn_refresh_status)

        main_layout.addWidget(status_group)

        cache_group = QGroupBox("Don cache an toan cho livestream")
        cache_layout = QVBoxLayout(cache_group)

        self.cache_info = QLabel("Cache: chua quet")
        self.cache_info.setStyleSheet("font-size: 15px;")
        cache_layout.addWidget(self.cache_info)

        cache_keep_layout = QHBoxLayout()
        cache_keep_layout.addWidget(QLabel("Giu lai cache trong so ngay gan nhat:"))

        self.spin_keep_cache_days = QSpinBox()
        self.spin_keep_cache_days.setRange(0, 3650)
        self.spin_keep_cache_days.setValue(7)
        cache_keep_layout.addWidget(self.spin_keep_cache_days)
        cache_keep_layout.addWidget(QLabel("0 = xoa toan bo cache an toan"))
        cache_layout.addLayout(cache_keep_layout)

        cache_btn_layout = QHBoxLayout()

        self.btn_scan_cache = QPushButton("Quet cache")
        self.btn_clean_cache = QPushButton("Don cache an toan")
        self.btn_scan_cache.clicked.connect(self.scan_cache_ui)
        self.btn_clean_cache.clicked.connect(self.clean_cache_ui)

        cache_btn_layout.addWidget(self.btn_scan_cache)
        cache_btn_layout.addWidget(self.btn_clean_cache)
        cache_layout.addLayout(cache_btn_layout)

        info = QLabel(
            "SAFE MODE: browser dang mo -> chi don GPUCache, Code Cache, ShaderCache, Crashpad.\n"
            "DEEP MODE: browser da tat -> don them Cache, Media Cache.\n"
            "Khong xoa cookie, session, mat khau, history, profile."
        )
        info.setStyleSheet("color: #555; font-size: 13px;")
        cache_layout.addWidget(info)

        main_layout.addWidget(cache_group)

        file_group = QGroupBox("Don file cu theo so ngay giu lai - Multi thu muc")
        file_layout = QVBoxLayout(file_group)

        self.folder_list = QListWidget()
        self.folder_list.setMinimumHeight(95)
        file_layout.addWidget(self.folder_list)

        folder_btn_layout = QHBoxLayout()
        self.btn_add_folder = QPushButton("Them thu muc")
        self.btn_remove_folder = QPushButton("Xoa thu muc da chon")
        self.btn_clear_folders = QPushButton("Xoa toan bo danh sach")

        self.btn_add_folder.clicked.connect(self.add_folder)
        self.btn_remove_folder.clicked.connect(self.remove_selected_folder)
        self.btn_clear_folders.clicked.connect(self.clear_folders)

        folder_btn_layout.addWidget(self.btn_add_folder)
        folder_btn_layout.addWidget(self.btn_remove_folder)
        folder_btn_layout.addWidget(self.btn_clear_folders)
        file_layout.addLayout(folder_btn_layout)

        day_layout = QHBoxLayout()
        day_layout.addWidget(QLabel("Giu lai file trong so ngay gan nhat:"))

        self.spin_keep_days = QSpinBox()
        self.spin_keep_days.setRange(1, 3650)
        self.spin_keep_days.setValue(60)
        day_layout.addWidget(self.spin_keep_days)

        self.chk_recycle = QCheckBox("Dua vao Recycle Bin")
        self.chk_recycle.setChecked(True)
        day_layout.addWidget(self.chk_recycle)

        file_layout.addLayout(day_layout)

        self.old_file_info = QLabel("File cu: chua quet")
        file_layout.addWidget(self.old_file_info)

        file_btn_layout = QHBoxLayout()
        self.btn_scan_old = QPushButton("Quet file cu")
        self.btn_clean_old = QPushButton("Don file cu")

        self.btn_scan_old.clicked.connect(self.scan_old_files)
        self.btn_clean_old.clicked.connect(self.clean_old_files)

        file_btn_layout.addWidget(self.btn_scan_old)
        file_btn_layout.addWidget(self.btn_clean_old)
        file_layout.addLayout(file_btn_layout)

        main_layout.addWidget(file_group)

        auto_group = QGroupBox("Tu dong")
        auto_layout = QVBoxLayout(auto_group)

        auto_check_layout = QHBoxLayout()
        self.chk_autostart = QCheckBox("Tu khoi dong cung Windows")
        self.chk_autoclean = QCheckBox("Tu dong don cache khi livestream")
        auto_check_layout.addWidget(self.chk_autostart)
        auto_check_layout.addWidget(self.chk_autoclean)
        auto_layout.addLayout(auto_check_layout)

        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Don cache moi phut:"))

        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(5, 1440)
        self.spin_interval.setValue(60)
        interval_layout.addWidget(self.spin_interval)
        auto_layout.addLayout(interval_layout)

        disk_warning_layout = QHBoxLayout()
        self.chk_disable_disk_warning = QCheckBox("Tat canh bao dung luong thap")
        disk_warning_layout.addWidget(self.chk_disable_disk_warning)
        disk_warning_layout.addWidget(QLabel("Canh bao khi con duoi GB:"))

        self.spin_disk_warning_gb = QSpinBox()
        self.spin_disk_warning_gb.setRange(1, 999)
        self.spin_disk_warning_gb.setValue(5)
        disk_warning_layout.addWidget(self.spin_disk_warning_gb)
        auto_layout.addLayout(disk_warning_layout)

        self.chk_disable_disk_warning.stateChanged.connect(self.queue_config_save)
        self.spin_disk_warning_gb.valueChanged.connect(self.queue_config_save)
        self.chk_autostart.stateChanged.connect(self.toggle_autostart)
        self.chk_autoclean.stateChanged.connect(self.toggle_auto_clean)
        self.spin_interval.valueChanged.connect(self.handle_interval_change)
        self.spin_keep_cache_days.valueChanged.connect(self.queue_config_save)
        self.spin_keep_days.valueChanged.connect(self.queue_config_save)
        self.chk_recycle.stateChanged.connect(self.queue_config_save)

        main_layout.addWidget(auto_group)

        self.status_info = QLabel("San sang")
        self.status_info.setStyleSheet("color: #198754; font-weight: bold;")
        main_layout.addWidget(self.status_info)

        self.btn_save = QPushButton("Luu cau hinh")
        self.btn_save.setStyleSheet(
            """
            QPushButton {
                background-color:#198754;
                color:white;
                font-size:18px;
                font-weight:bold;
                padding:12px;
                border-radius:7px;
            }
            QPushButton:hover {
                background-color:#157347;
            }
            """
        )
        self.btn_save.clicked.connect(self.save_config)
        main_layout.addWidget(self.btn_save)

        footer = QHBoxLayout()
        footer.addWidget(QLabel("ATG Safe Cache Cleaner | Version 1.0.0"))
        footer.addStretch()
        main_layout.addLayout(footer)

    def log(self, text):
        message = str(text)
        write_log(message)
        self.status_info.setText(message)

    def queue_config_save(self, *args):
        if self.loading_ui:
            return

        self.config_save_timer.start(CONFIG_SAVE_DEBOUNCE_MS)

    def handle_interval_change(self, value):
        if self.chk_autoclean.isChecked():
            self.auto_timer.start(value * 60 * 1000)
            self.status_info.setText(f"Da cap nhat chu ky tu dong don: {value} phut")

        self.queue_config_save()

    def refresh_browser_status(self):
        text = browser_status_text()
        ram_text = get_browser_memory_text()
        mode = get_clean_mode()

        self.browser_status.setText(text)
        self.browser_memory.setText(ram_text)
        self.status_info.setText(f"Che do hien tai: {mode}")

    def start_watchdog(self):
        self.watchdog_timer.start(WATCHDOG_INTERVAL_MS)
        self.log("Watchdog da khoi dong")

    def watchdog_check(self):
        if self.cleaning_in_progress:
            self.watchdog_info.setText("Watchdog: dang cho lan don hien tai hoan tat")
            return

        busy, busy_msg = is_system_busy()

        if busy:
            self.watchdog_info.setText(f"Tam dung clean: {busy_msg}")
            self.log(f"Watchdog pause: {busy_msg}")
            return

        high_ram, browser, memory = is_browser_memory_high(WATCHDOG_BROWSER_RAM_LIMIT_GB)

        if high_ram:
            message = f"RAM browser cao: {browser} | {format_ram(memory)}"
            self.watchdog_info.setText(message)
            self.log(message)

            if self.can_watchdog_clean():
                self.clean_cache_ui()
            else:
                self.log("Watchdog cooldown...")

            return

        cache_metrics = get_cache_metrics()
        danger_size = cache_metrics["danger_size"]
        danger_files = cache_metrics["danger_files"]

        if danger_size >= WATCHDOG_DANGER_CACHE_LIMIT_BYTES:
            message = (
                f"GPUCache/Code Cache cao: {format_size(danger_size)} | "
                f"{danger_files} file"
            )
            self.watchdog_info.setText(message)
            self.log(message)

            if self.can_watchdog_clean():
                self.clean_cache_ui()
            else:
                self.log("Watchdog cooldown...")

            return

        self.watchdog_info.setText(
            "Watchdog OK | Cache: "
            f"{format_size(cache_metrics['total_size'])} | "
            f"{cache_metrics['total_files']} file"
        )

    def can_watchdog_clean(self):
        now = time.time()

        if now - self.last_watchdog_clean < WATCHDOG_CLEAN_COOLDOWN_SECONDS:
            return False

        self.last_watchdog_clean = now
        return True

    def scan_cache_ui(self):
        if self.cleaning_in_progress:
            self.log("Dang don cache, tam thoi bo qua lenh quet")
            return

        keep_days = self.spin_keep_cache_days.value()
        targets, size, files = scan_cache(keep_days)
        mode = get_clean_mode()

        self.cache_info.setText(
            f"[{mode}] Cache co the don: {files} file | {format_size(size)}"
        )
        self.log(
            f"[{mode}] Quet cache: {files} file | {format_size(size)} | "
            f"Giu lai {keep_days} ngay | Thu muc: {len(targets)}"
        )

    def clean_cache_ui(self):
        if self.cleaning_in_progress:
            self.log("Dang co tac vu don cache khac, bo qua lan nay")
            return

        keep_days = self.spin_keep_cache_days.value()
        self.cleaning_in_progress = True

        try:
            deleted_size, deleted_files, skipped, mode = clean_cache(
                keep_days=keep_days,
                log_callback=self.log,
            )

            self.cache_info.setText(
                f"[{mode}] Da don: {deleted_files} file | "
                f"{format_size(deleted_size)} | Bo qua: {skipped}"
            )
        finally:
            self.cleaning_in_progress = False

        self.refresh_browser_status()

    def scan_old_files(self):
        folders = self.get_selected_folders()

        if not folders:
            QMessageBox.warning(self, "Thieu thu muc", "Ban chua them thu muc can don.")
            return

        keep_days = self.spin_keep_days.value()
        total_files = 0
        total_size = 0

        for folder in folders:
            files, size = summarize_old_files(folder, keep_days)
            total_files += files
            total_size += size

            self.log(
                f"Quet: {folder} | {files} file cu hon {keep_days} ngay | "
                f"{format_size(size)}"
            )

        self.old_file_info.setText(
            f"Tong: {total_files} file cu hon {keep_days} ngay | {format_size(total_size)}"
        )

    def clean_old_files(self):
        folders = self.get_selected_folders()

        if not folders:
            QMessageBox.warning(self, "Thieu thu muc", "Ban chua them thu muc can don.")
            return

        keep_days = self.spin_keep_days.value()
        recycle = self.chk_recycle.isChecked()

        confirm = QMessageBox.question(
            self,
            "Xac nhan",
            f"Don file cu hon {keep_days} ngay trong {len(folders)} thu muc?",
        )

        if confirm != QMessageBox.Yes:
            return

        total_deleted_size = 0
        total_deleted_files = 0
        total_skipped = 0

        for folder in folders:
            self.log(f"Dang don thu muc: {folder}")

            deleted_size, deleted_files, skipped = clean_old_files(
                folder,
                keep_days,
                recycle,
                self.log,
            )

            total_deleted_size += deleted_size
            total_deleted_files += deleted_files
            total_skipped += skipped

        self.old_file_info.setText(
            f"Da don tong: {total_deleted_files} file | "
            f"{format_size(total_deleted_size)} | Bo qua: {total_skipped}"
        )

    def toggle_autostart(self):
        try:
            if self.chk_autostart.isChecked():
                enable_autostart()
                self.log("Da bat tu khoi dong cung Windows")
            else:
                disable_autostart()
                self.log("Da tat tu khoi dong cung Windows")
        except Exception as exc:
            self.log(f"Loi autostart: {exc}")

        self.queue_config_save()

    def toggle_auto_clean(self):
        if self.chk_autoclean.isChecked():
            minutes = self.spin_interval.value()
            self.auto_timer.start(minutes * 60 * 1000)
            self.log(f"Da bat tu dong don cache moi {minutes} phut")
        else:
            self.auto_timer.stop()
            self.log("Da tat tu dong don cache")

        self.queue_config_save()

    def auto_clean_task(self):
        if self.cleaning_in_progress:
            self.log("Bo qua auto clean vi dang co tac vu don")
            return

        self.log("Dang tu dong don cache an toan...")
        self.clean_cache_ui()

    def default_config(self):
        return {
            "old_file_folders": [],
            "autostart": False,
            "keep_days": 60,
            "keep_cache_days": 7,
            "recycle_bin": True,
            "auto_clean": False,
            "auto_interval": 60,
            "disk_warning_gb": 5,
            "disable_disk_warning": False,
        }

    def load_config(self):
        default = self.default_config()
        path = Path(CONFIG_FILE)

        try:
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)

                with open(path, "w", encoding="utf-8") as file_obj:
                    json.dump(default, file_obj, indent=4, ensure_ascii=False)

                return default

            with open(path, "r", encoding="utf-8") as file_obj:
                data = json.load(file_obj)

            if isinstance(data, dict):
                default.update(data)

        except Exception as exc:
            write_log(f"Loi load config: {exc}")

        return default

    def get_selected_folders(self):
        return [
            self.folder_list.item(index).text()
            for index in range(self.folder_list.count())
        ]

    def save_config(self, *args):
        if self.loading_ui:
            return

        try:
            self.config["old_file_folders"] = self.get_selected_folders()
            self.config["autostart"] = self.chk_autostart.isChecked()
            self.config["keep_days"] = self.spin_keep_days.value()
            self.config["keep_cache_days"] = self.spin_keep_cache_days.value()
            self.config["recycle_bin"] = self.chk_recycle.isChecked()
            self.config["auto_clean"] = self.chk_autoclean.isChecked()
            self.config["auto_interval"] = self.spin_interval.value()
            self.config["disable_disk_warning"] = self.chk_disable_disk_warning.isChecked()
            self.config["disk_warning_gb"] = self.spin_disk_warning_gb.value()

            path = Path(CONFIG_FILE)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding="utf-8") as file_obj:
                json.dump(self.config, file_obj, indent=4, ensure_ascii=False)

            self.status_info.setText(f"Da luu cau hinh: {path}")
        except Exception as exc:
            self.log(f"Loi luu config: {exc}")

    def load_ui_state(self):
        self.folder_list.clear()

        for folder in self.config.get("old_file_folders", []):
            self.folder_list.addItem(folder)

        self.spin_keep_days.setValue(self.config.get("keep_days", 60))
        self.spin_keep_cache_days.setValue(self.config.get("keep_cache_days", 7))
        self.chk_recycle.setChecked(self.config.get("recycle_bin", True))
        self.chk_disable_disk_warning.setChecked(
            self.config.get("disable_disk_warning", False)
        )
        self.spin_interval.setValue(self.config.get("auto_interval", 60))
        self.spin_disk_warning_gb.setValue(self.config.get("disk_warning_gb", 5))

        self.chk_autoclean.blockSignals(True)
        self.chk_autoclean.setChecked(self.config.get("auto_clean", False))
        self.chk_autoclean.blockSignals(False)

        if self.chk_autoclean.isChecked():
            self.auto_timer.start(self.spin_interval.value() * 60 * 1000)
        else:
            self.auto_timer.stop()

        config_wants_autostart = self.config.get("autostart", False)
        autostart_enabled = False

        try:
            autostart_enabled = is_autostart_enabled()

            if config_wants_autostart and not autostart_enabled:
                enable_autostart()
                autostart_enabled = is_autostart_enabled()

            self.chk_autostart.blockSignals(True)
            self.chk_autostart.setChecked(autostart_enabled)
            self.chk_autostart.blockSignals(False)
            self.config["autostart"] = autostart_enabled
        except Exception as exc:
            self.chk_autostart.blockSignals(False)
            self.chk_autostart.setChecked(False)
            write_log(f"Loi dong bo autostart: {exc}")

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chon thu muc can don file cu")

        if not folder:
            return

        folders = self.get_selected_folders()

        if folder in folders:
            self.log(f"Thu muc da co trong danh sach: {folder}")
            return

        self.folder_list.addItem(folder)
        self.queue_config_save()
        self.log(f"Da them thu muc: {folder}")

    def remove_selected_folder(self):
        selected_items = self.folder_list.selectedItems()

        if not selected_items:
            QMessageBox.warning(self, "Chua chon", "Ban chua chon thu muc can xoa.")
            return

        for item in selected_items:
            folder = item.text()
            row = self.folder_list.row(item)
            self.folder_list.takeItem(row)
            self.log(f"Da xoa khoi danh sach: {folder}")

        self.queue_config_save()

    def clear_folders(self):
        confirm = QMessageBox.question(
            self,
            "Xac nhan",
            "Ban co chac muon xoa toan bo danh sach thu muc khong?",
        )

        if confirm != QMessageBox.Yes:
            return

        self.folder_list.clear()
        self.queue_config_save()
        self.log("Da xoa toan bo danh sach thu muc")

    def check_disk_space(self):
        if self.chk_disable_disk_warning.isChecked():
            return

        folders = self.get_selected_folders()

        if not folders:
            return

        limit_gb = self.spin_disk_warning_gb.value()
        drive_to_folder = {}

        for folder in folders:
            drive = Path(folder).anchor or folder

            if drive not in drive_to_folder:
                drive_to_folder[drive] = folder

        now = time.time()

        for drive, folder in drive_to_folder.items():
            low, free_gb = is_disk_low(folder, limit_gb=limit_gb)

            if not low:
                self.last_disk_alert_at.pop(drive, None)
                continue

            last_alert = self.last_disk_alert_at.get(drive, 0.0)

            if now - last_alert < DISK_ALERT_COOLDOWN_SECONDS:
                self.status_info.setText(
                    f"Canh bao dung luong thap: {drive} con {free_gb:.2f} GB"
                )
                continue

            self.last_disk_alert_at[drive] = now
            message = (
                f"O dia chi con {free_gb:.2f} GB. "
                f"Nguong canh bao: duoi {limit_gb} GB."
            )
            self.log(message)

            try:
                if self.disk_low_sound is not None:
                    self.disk_low_sound.play()
            except Exception:
                pass

            QMessageBox.warning(
                self,
                "Canh bao dung luong thap",
                f"Thu muc:\n{folder}\n\n"
                f"O dia chi con {free_gb:.2f} GB.\n"
                f"Nguong canh bao: duoi {limit_gb} GB.\n"
                f"Nen don dep hoac chuyen du lieu.",
            )

            return

    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(resource_path(ICON_FILE)))
        self.tray_icon.setToolTip("ATG Safe Cache Cleaner")

        self.tray_menu = QMenu()

        action_show = QAction("Mo phan mem", self)
        action_exit = QAction("Thoat hoan toan", self)

        action_show.triggered.connect(self.show_normal)
        action_exit.triggered.connect(self.exit_app)

        self.tray_menu.addAction(action_show)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(action_exit)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def show_normal(self):
        self.show()
        self.setWindowState(Qt.WindowNoState)
        self.activateWindow()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.tray_menu.popup(QCursor.pos())
        elif reason == QSystemTrayIcon.DoubleClick:
            self.show_normal()

    def exit_app(self):
        self.is_quitting = True
        self.allow_close_to_tray = False

        for timer in (
            self.auto_timer,
            self.watchdog_timer,
            self.disk_timer,
            self.config_save_timer,
        ):
            try:
                timer.stop()
            except Exception:
                pass

        try:
            self.tray_icon.hide()
            self.tray_icon.deleteLater()
        except Exception:
            pass

        QApplication.quit()

    def closeEvent(self, event):
        if self.is_quitting or not self.allow_close_to_tray:
            event.accept()
            return

        event.ignore()
        self.hide()

        if hasattr(self, "tray_icon"):
            self.tray_icon.showMessage(
                "ATG Safe Cache Cleaner",
                "Phan mem van dang chay nen. Click icon tray de mo hoac thoat.",
                QSystemTrayIcon.Information,
                3000,
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    icon_path = resource_path(ICON_FILE)

    if Path(icon_path).exists():
        app.setWindowIcon(QIcon(icon_path))

    ok, _msg = check_license()

    if not ok:
        dialog = LicenseDialog()
        dialog.exec()
        sys.exit()

    window = MainWindow()

    if is_windows_startup():
        window.hide()

        QTimer.singleShot(
            2000,
            lambda: window.tray_icon.showMessage(
                "ATG Safe Cache Cleaner",
                "Da khoi dong nen cung Windows\nWatchdog dang hoat dong",
                QSystemTrayIcon.Information,
                5000,
            ),
        )
    else:
        window.show()

    sys.exit(app.exec())
