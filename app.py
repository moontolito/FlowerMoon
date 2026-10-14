"""PDF Analyzer desktop entry point — pure Python/PySide6."""

from __future__ import annotations

import argparse
import sys
import traceback

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

from pdf_analyzer.ui import MainWindow


APP_VERSION = "0.26.0-m4a"


def apply_white_theme(application: QApplication) -> None:
    application.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#25313d"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f4f6f8"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#25313d"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#25313d"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#25313d"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2d7ed8"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#9aa5af"))
    application.setPalette(palette)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PDF Analyzer — local PDF reader")
    parser.add_argument("pdf", nargs="?", help="Optional PDF file to open")
    return parser.parse_args()


def run() -> int:
    args = parse_args()
    application = QApplication(sys.argv[:1])
    application.setApplicationName("PDF Analyzer")
    application.setApplicationVersion(APP_VERSION)
    application.setOrganizationName("PDF Analyzer")
    apply_white_theme(application)

    def handle_exception(exc_type, exc_value, exc_traceback):
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        print(details, file=sys.stderr)
        QMessageBox.critical(None, "Unexpected error", str(exc_value))

    sys.excepthook = handle_exception
    window = MainWindow(version=APP_VERSION)
    window.show()
    if args.pdf:
        window.open_path(args.pdf)
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(run())
