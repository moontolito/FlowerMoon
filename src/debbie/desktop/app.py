"""Debbie Desktop process entry point."""

from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication, QTimer, Qt
from PySide6.QtWidgets import QApplication

from .main_window import DebbieMainWindow


def create_application(argv: list[str] | None = None) -> QApplication:
    QCoreApplication.setApplicationName("Debbie")
    QCoreApplication.setOrganizationName("FlowerMoon")
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    return QApplication.instance() or QApplication(argv if argv is not None else sys.argv)


def main() -> int:
    smoke_test = "--smoke-test" in sys.argv
    arguments = [value for value in sys.argv if value != "--smoke-test"]
    application = create_application(arguments)
    window = DebbieMainWindow()
    window.show()
    if smoke_test:
        QTimer.singleShot(0, window.close)
    return application.exec()
