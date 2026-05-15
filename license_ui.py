from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QApplication,
)

from license_manager import get_machine_code


class LicenseDialog(QDialog):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Kích hoạt License")

        layout = QVBoxLayout(self)

        machine = get_machine_code()

        label = QLabel(
            f"Mã license:\n\n{machine}"
        )

        layout.addWidget(label)

        btn_copy = QPushButton(
            "Copy mã license gửi về Zalo 0904143113 để được cấp license"
        )

        btn_copy.clicked.connect(
            lambda: QApplication.clipboard().setText(machine)
        )

        layout.addWidget(btn_copy)