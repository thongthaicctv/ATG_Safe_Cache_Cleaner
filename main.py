import json
import sys
import time


from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QCheckBox,
  
    QFileDialog,
    QSpinBox,
    QMessageBox,
    QGroupBox,
    QListWidget,
)

from safe_cleaner import scan_cache, clean_cache, format_size
from file_cleaner import find_old_files, clean_old_files
from browser_detector import browser_status_text, get_clean_mode
from autostart import enable_autostart, disable_autostart, is_autostart_enabled
from app_logger import write_log


from PySide6.QtWidgets import (
    QSystemTrayIcon,
    QMenu
)
from PySide6.QtGui import QAction, QCursor


from browser_watchdog import get_browser_memory_text
from browser_watchdog import (
    is_browser_memory_high,
    format_size as format_ram,
)

from cache_watchdog import (
    is_cache_high,
    get_total_cache_size,
)

from cache_watchdog import (
    is_danger_cache_high,
)

from system_watchdog import is_system_busy

from cache_watchdog import (
    is_danger_cache_high,
    get_total_cache_size,
)

from license_manager import check_license
from license_ui import LicenseDialog


CONFIG_FILE = "config.json"
ICON_FILE = "assets/icon.ico"
LOGO_FILE = "assets/logo.png"


def resource_path(relative_path: str) -> str:
    base_path = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return str(Path(base_path) / relative_path)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.is_quitting = False
        
        self.last_watchdog_clean = 0

        self.setWindowTitle("ATG Safe Cache Cleaner")
        self.resize(820, 720)

        icon_path = resource_path(ICON_FILE)
        if Path(icon_path).exists():
            self.setWindowIcon(QIcon(icon_path))

        self.config = self.load_config()

        self.auto_timer = QTimer()
        self.auto_timer.timeout.connect(self.auto_clean_task)

        self.init_ui()
        self.load_ui_state()
        self.refresh_browser_status()

        self.setup_tray()


        self.watchdog_timer = QTimer()
        self.watchdog_timer.timeout.connect(
            self.watchdog_check
        )

        self.watchdog_timer.start(30000)
    
    def watchdog_check(self):

        # 1. Nếu CPU/RAM hệ thống đang cao thì không clean
        busy, busy_msg = is_system_busy()

        if busy:
            self.watchdog_info.setText(f"Tạm dừng clean: {busy_msg}")
            self.log(f"Watchdog pause: {busy_msg}")
            return

        # 2. Kiểm tra RAM browser
        high_ram, browser, memory = is_browser_memory_high(6)

        if high_ram:
            msg = f"RAM browser cao: {browser} | {format_ram(memory)}"
            self.watchdog_info.setText(msg)
            self.log(msg)

            if self.can_watchdog_clean():
                self.clean_cache_ui()
            else:
                self.log("Watchdog cooldown...")

            return

        # 3. Kiểm tra GPUCache / Code Cache
        danger_high, danger_size, danger_files = is_danger_cache_high(1)

        if danger_high:
            msg = f"GPUCache/Code Cache cao: {format_size(danger_size)} | {danger_files} file"
            self.watchdog_info.setText(msg)
            self.log(msg)

            if self.can_watchdog_clean():
                self.clean_cache_ui()
            else:
                self.log("Watchdog cooldown...")

            return

        # 4. Trạng thái bình thường
        total_size, total_files = get_total_cache_size()

        self.watchdog_info.setText(
            f"Watchdog OK | Cache: {format_size(total_size)} | {total_files} file"
        )
        


    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # ================= HEADER =================
        header = QHBoxLayout()

        logo = QLabel()
        logo_path = resource_path(LOGO_FILE)
        if Path(logo_path).exists():
            pix = QPixmap(logo_path).scaled(
                54,
                54,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            logo.setPixmap(pix)

        header.addWidget(logo)

        title = QLabel("ATG Safe Browser Cache Cleaner")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size: 24px; font-weight: bold; color: #0B5ED7;"
        )
        header.addWidget(title, 1)

        main_layout.addLayout(header)

        # ================= BROWSER STATUS =================
        status_group = QGroupBox("Trạng thái trình duyệt")
        status_layout = QVBoxLayout(status_group)

        self.browser_status = QLabel("Đang kiểm tra...")

        self.browser_memory = QLabel("RAM trình duyệt: Đang kiểm tra...")
        self.browser_memory.setStyleSheet(
            "font-size: 13px; color: #0B5ED7;"
        )

        self.watchdog_info = QLabel(
            "Watchdog: Đang theo dõi..."
        )

        self.watchdog_info.setStyleSheet(
            "font-size: 13px; color: #198754;"
        )

        status_layout.addWidget(
            self.watchdog_info
        )



        status_layout.addWidget(self.browser_memory)


        self.browser_status.setStyleSheet("font-size: 14px;")
        status_layout.addWidget(self.browser_status)

        self.btn_refresh_status = QPushButton("🔄 Kiểm tra trạng thái trình duyệt")
        self.btn_refresh_status.clicked.connect(self.refresh_browser_status)
        status_layout.addWidget(self.btn_refresh_status)

        main_layout.addWidget(status_group)

        # ================= CACHE GROUP =================
        cache_group = QGroupBox("Dọn cache an toàn cho livestream")
        cache_layout = QVBoxLayout(cache_group)

        self.cache_info = QLabel("Cache: Chưa quét")
        self.cache_info.setStyleSheet("font-size: 15px;")
        cache_layout.addWidget(self.cache_info)

        cache_keep_layout = QHBoxLayout()
        cache_keep_layout.addWidget(QLabel("Giữ lại cache trong số ngày gần nhất:"))

        self.spin_keep_cache_days = QSpinBox()
        self.spin_keep_cache_days.setRange(0, 3650)
        self.spin_keep_cache_days.setValue(7)
        cache_keep_layout.addWidget(self.spin_keep_cache_days)

        cache_keep_layout.addWidget(QLabel("0 = xoá toàn bộ cache an toàn"))
        cache_layout.addLayout(cache_keep_layout)

        cache_btn_layout = QHBoxLayout()

        self.btn_scan_cache = QPushButton("🔍 Quét cache")
        self.btn_clean_cache = QPushButton("🧹 Dọn cache an toàn")

        self.btn_scan_cache.clicked.connect(self.scan_cache_ui)
        self.btn_clean_cache.clicked.connect(self.clean_cache_ui)

        cache_btn_layout.addWidget(self.btn_scan_cache)
        cache_btn_layout.addWidget(self.btn_clean_cache)

        cache_layout.addLayout(cache_btn_layout)

        info = QLabel(
            "SAFE MODE: trình duyệt đang mở → chỉ dọn GPUCache, Code Cache, ShaderCache, Crashpad.\n"
            "DEEP MODE: trình duyệt đã tắt → dọn thêm Cache, Media Cache.\n"
            "Không xoá cookie, session, mật khẩu, history, profile."
        )
        info.setStyleSheet("color: #555; font-size: 13px;")
        cache_layout.addWidget(info)

        main_layout.addWidget(cache_group)

        # ================= OLD FILE GROUP =================
        file_group = QGroupBox("Dọn file cũ theo số ngày giữ lại - Multi thư mục")
        file_layout = QVBoxLayout(file_group)

        self.folder_list = QListWidget()
        self.folder_list.setMinimumHeight(95)
        file_layout.addWidget(self.folder_list)

        folder_btn_layout = QHBoxLayout()

        self.btn_add_folder = QPushButton("📁 Thêm thư mục")
        self.btn_remove_folder = QPushButton("🗑 Xoá thư mục đã chọn")
        self.btn_clear_folders = QPushButton("🗑 Xoá toàn bộ danh sách")

        self.btn_add_folder.clicked.connect(self.add_folder)
        self.btn_remove_folder.clicked.connect(self.remove_selected_folder)
        self.btn_clear_folders.clicked.connect(self.clear_folders)

        folder_btn_layout.addWidget(self.btn_add_folder)
        folder_btn_layout.addWidget(self.btn_remove_folder)
        folder_btn_layout.addWidget(self.btn_clear_folders)

        file_layout.addLayout(folder_btn_layout)

        day_layout = QHBoxLayout()
        day_layout.addWidget(QLabel("Giữ lại file trong số ngày gần nhất:"))

        self.spin_keep_days = QSpinBox()
        self.spin_keep_days.setRange(1, 3650)
        self.spin_keep_days.setValue(60)
        day_layout.addWidget(self.spin_keep_days)

        self.chk_recycle = QCheckBox("Đưa vào Recycle Bin")
        self.chk_recycle.setChecked(True)
        day_layout.addWidget(self.chk_recycle)

        file_layout.addLayout(day_layout)

        self.old_file_info = QLabel("File cũ: Chưa quét")
        file_layout.addWidget(self.old_file_info)

        file_btn_layout = QHBoxLayout()

        self.btn_scan_old = QPushButton("🔍 Quét file cũ")
        self.btn_clean_old = QPushButton("🗑 Dọn file cũ")

        self.btn_scan_old.clicked.connect(self.scan_old_files)
        self.btn_clean_old.clicked.connect(self.clean_old_files)

        file_btn_layout.addWidget(self.btn_scan_old)
        file_btn_layout.addWidget(self.btn_clean_old)

        file_layout.addLayout(file_btn_layout)

        main_layout.addWidget(file_group)

        # ================= AUTO GROUP =================
        auto_group = QGroupBox("Tự động")
        auto_layout = QVBoxLayout(auto_group)

        auto_check_layout = QHBoxLayout()

        self.chk_autostart = QCheckBox("Tự khởi động cùng Windows")
        self.chk_autoclean = QCheckBox("Tự động dọn cache khi livestream")

        auto_check_layout.addWidget(self.chk_autostart)
        auto_check_layout.addWidget(self.chk_autoclean)

        auto_layout.addLayout(auto_check_layout)

        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Dọn cache mỗi phút:"))

        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(5, 1440)
        self.spin_interval.setValue(60)

        interval_layout.addWidget(self.spin_interval)
        auto_layout.addLayout(interval_layout)

        self.chk_autostart.stateChanged.connect(self.toggle_autostart)
        self.chk_autoclean.stateChanged.connect(self.toggle_auto_clean)
        self.spin_interval.valueChanged.connect(self.save_config)
        self.spin_keep_cache_days.valueChanged.connect(self.save_config)

        main_layout.addWidget(auto_group)

        # STATUS LABEL
        self.status_info = QLabel("Sẵn sàng")
        self.status_info.setStyleSheet(
            "color: #198754; font-weight: bold;"
        )

        main_layout.addWidget(self.status_info)

        
        # ================= SAVE =================
        self.btn_save = QPushButton("💾 Lưu cấu hình")
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

        # ================= FOOTER =================
        footer = QHBoxLayout()
        footer.addWidget(QLabel("ATG Safe Cache Cleaner | Phiên bản 1.0.0"))
        footer.addStretch()
        main_layout.addLayout(footer)

    def log(self, text):

        text = str(text)

        write_log(text)

        self.status_info.setText(text)

    def refresh_browser_status(self):

        text = browser_status_text()

        ram_text = get_browser_memory_text()

        mode = get_clean_mode()

        self.browser_status.setText(text)

        self.browser_memory.setText(ram_text)

        self.log(f"Chế độ hiện tại: {mode}")


        text = browser_status_text()
        mode = get_clean_mode()
        self.browser_status.setText(text)
        self.log(f"Chế độ hiện tại: {mode}")

    def scan_cache_ui(self):
        keep_days = self.spin_keep_cache_days.value()
        targets, size, files = scan_cache(keep_days)
        mode = get_clean_mode()

        self.cache_info.setText(
            f"[{mode}] Cache có thể dọn: {files} file | {format_size(size)}"
        )

        self.log(
            f"[{mode}] Quét cache: {files} file | {format_size(size)} | "
            f"Giữ lại {keep_days} ngày | Thư mục: {len(targets)}"
        )

    def clean_cache_ui(self):
        keep_days = self.spin_keep_cache_days.value()

        deleted_size, deleted_files, skipped, mode = clean_cache(
            keep_days=keep_days,
            log_callback=self.log,
        )

        self.cache_info.setText(
            f"[{mode}] Đã dọn: {deleted_files} file | "
            f"{format_size(deleted_size)} | Bỏ qua: {skipped}"
        )

        self.refresh_browser_status()

    def scan_old_files(self):
        folders = self.config.get("old_file_folders", [])

        if not folders:
            QMessageBox.warning(self, "Thiếu thư mục", "Bạn chưa thêm thư mục cần dọn.")
            return

        keep_days = self.spin_keep_days.value()
        total_files = 0
        total_size = 0

        for folder in folders:
            files, size = find_old_files(folder, keep_days)
            total_files += len(files)
            total_size += size

            self.log(
                f"Quét: {folder} | "
                f"{len(files)} file cũ hơn {keep_days} ngày | "
                f"{format_size(size)}"
            )

        self.old_file_info.setText(
            f"Tổng: {total_files} file cũ hơn {keep_days} ngày | {format_size(total_size)}"
        )

    def clean_old_files(self):
        folders = self.config.get("old_file_folders", [])

        if not folders:
            QMessageBox.warning(self, "Thiếu thư mục", "Bạn chưa thêm thư mục cần dọn.")
            return

        keep_days = self.spin_keep_days.value()
        recycle = self.chk_recycle.isChecked()

        confirm = QMessageBox.question(
            self,
            "Xác nhận",
            f"Dọn file cũ hơn {keep_days} ngày trong {len(folders)} thư mục?",
        )

        if confirm != QMessageBox.Yes:
            return

        total_deleted_size = 0
        total_deleted_files = 0
        total_skipped = 0

        for folder in folders:
            self.log(f"Đang dọn thư mục: {folder}")

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
            f"Đã dọn tổng: {total_deleted_files} file | "
            f"{format_size(total_deleted_size)} | Bỏ qua: {total_skipped}"
        )

    def toggle_autostart(self):
        try:
            if self.chk_autostart.isChecked():
                enable_autostart()
                self.log("Đã bật tự khởi động cùng Windows")
            else:
                disable_autostart()
                self.log("Đã tắt tự khởi động cùng Windows")
        except Exception as e:
            self.log(f"Lỗi autostart: {e}")

        self.save_config()

    def toggle_auto_clean(self):
        if self.chk_autoclean.isChecked():
            minutes = self.spin_interval.value()
            self.auto_timer.start(minutes * 60 * 1000)
            self.log(f"Đã bật tự động dọn cache mỗi {minutes} phút")
        else:
            self.auto_timer.stop()
            self.log("Đã tắt tự động dọn cache")

        self.save_config()

    def auto_clean_task(self):
        self.log("Đang tự động dọn cache an toàn...")
        self.clean_cache_ui()

    def load_config(self):
        default = {
            "old_file_folders": [],
            "keep_days": 60,
            "keep_cache_days": 7,
            "recycle_bin": True,
            "auto_clean": False,
            "auto_interval": 60,
        }

        path = Path(CONFIG_FILE)

        if not path.exists():
            return default

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                default.update(data)
        except Exception:
            pass

        return default

    def save_config(self):
        self.config["old_file_folders"] = [
            self.folder_list.item(i).text()
            for i in range(self.folder_list.count())
        ]
        self.config["keep_days"] = self.spin_keep_days.value()
        self.config["keep_cache_days"] = self.spin_keep_cache_days.value()
        self.config["recycle_bin"] = self.chk_recycle.isChecked()
        self.config["auto_clean"] = self.chk_autoclean.isChecked()
        self.config["auto_interval"] = self.spin_interval.value()

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

        self.log("Đã lưu cấu hình")

    def load_ui_state(self):
        self.folder_list.clear()

        for folder in self.config.get("old_file_folders", []):
            self.folder_list.addItem(folder)

        self.spin_keep_days.setValue(self.config.get("keep_days", 60))
        self.spin_keep_cache_days.setValue(self.config.get("keep_cache_days", 7))
        self.chk_recycle.setChecked(self.config.get("recycle_bin", True))
        self.spin_interval.setValue(self.config.get("auto_interval", 60))

        try:
            self.chk_autostart.setChecked(is_autostart_enabled())
        except Exception:
            self.chk_autostart.setChecked(False)

        if self.config.get("auto_clean", False):
            self.chk_autoclean.setChecked(True)
            self.toggle_auto_clean()

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục cần dọn file cũ")

        if not folder:
            return

        folders = self.config.get("old_file_folders", [])

        if folder not in folders:
            folders.append(folder)
            self.config["old_file_folders"] = folders
            self.folder_list.addItem(folder)
            self.save_config()
            self.log(f"Đã thêm thư mục: {folder}")
        else:
            self.log(f"Thư mục đã có trong danh sách: {folder}")

    def remove_selected_folder(self):
        selected_items = self.folder_list.selectedItems()

        if not selected_items:
            QMessageBox.warning(self, "Chưa chọn", "Bạn chưa chọn thư mục cần xoá.")
            return

        folders = self.config.get("old_file_folders", [])

        for item in selected_items:
            folder = item.text()

            if folder in folders:
                folders.remove(folder)

            row = self.folder_list.row(item)
            self.folder_list.takeItem(row)
            self.log(f"Đã xoá khỏi danh sách: {folder}")

        self.config["old_file_folders"] = folders
        self.save_config()

    def clear_folders(self):
        confirm = QMessageBox.question(
            self,
            "Xác nhận",
            "Bạn có chắc muốn xoá toàn bộ danh sách thư mục không?",
        )

        if confirm != QMessageBox.Yes:
            return

        self.folder_list.clear()
        self.config["old_file_folders"] = []
        self.save_config()
        self.log("Đã xoá toàn bộ danh sách thư mục")
    
    def can_watchdog_clean(self):

        cooldown = 10 * 60

        now = time.time()

        if now - self.last_watchdog_clean < cooldown:
            return False

        self.last_watchdog_clean = now

        return True


    def setup_tray(self):

        self.tray_icon = QSystemTrayIcon(self)

        icon_path = resource_path(ICON_FILE)

        self.tray_icon.setIcon(
            QIcon(icon_path)
        )

        self.tray_icon.setToolTip(
            "ATG Safe Cache Cleaner"
        )

        tray_menu = QMenu()

        action_show = QAction("Mở")
        action_quit = QAction("Thoát")

        action_show.triggered.connect(
            self.show_normal
        )

        action_quit.triggered.connect(
            self.quit_app
        )

        tray_menu.addAction(action_show)
        tray_menu.addSeparator()
        tray_menu.addAction(action_quit)

        self.tray_icon.setContextMenu(tray_menu)

        self.tray_menu = tray_menu

        self.tray_icon.activated.connect(
            self.on_tray_activated
        )

        self.tray_icon.show()

    def show_normal(self):

        self.show()

        self.setWindowState(
            Qt.WindowNoState
        )

        self.activateWindow()

    def quit_app(self):

        self.is_quitting = True

        if hasattr(self, "tray_icon"):
            self.tray_icon.hide()

        QApplication.quit()
        
    def on_tray_activated(self, reason):

        if reason == QSystemTrayIcon.Trigger:
            self.tray_menu.popup(QCursor.pos())

        elif reason == QSystemTrayIcon.DoubleClick:
            self.show_normal()

    
    """def closeEvent(self, event):

        self.is_quitting = True

        if hasattr(self, "tray_icon"):
            self.tray_icon.hide()

        event.accept()

    """
    
    def closeEvent(self, event):

        if self.is_quitting:
            event.accept()
            return

        event.ignore()

        self.hide()

        if hasattr(self, "tray_icon"):
            self.tray_icon.showMessage(
                "ATG Safe Cache Cleaner",
                "Ứng dụng vẫn đang chạy nền.",
                QSystemTrayIcon.Information,
                3000
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)

    icon_path = resource_path(ICON_FILE)
    print("ICON:", icon_path)
    print("EXISTS:", Path(icon_path).exists())
    if Path(icon_path).exists():
        app.setWindowIcon(QIcon(icon_path))

    ok, msg = check_license()

    if not ok:

        dlg = LicenseDialog()
        dlg.exec()

        sys.exit()

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
