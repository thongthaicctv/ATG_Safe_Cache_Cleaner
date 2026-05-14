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
            f"Mã máy:\n\n{machine}"
        )

        layout.addWidget(label)

        btn_copy = QPushButton(
            "Copy mã máy"
        )

        btn_copy.clicked.connect(
            lambda: QApplication.clipboard().setText(machine)
        )

        layout.addWidget(btn_copy)