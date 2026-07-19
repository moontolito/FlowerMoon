"""PySide6 desktop shell for Debbie's read-only MVP workflow."""

from .app import create_application, main
from .main_window import DebbieMainWindow

__all__ = ["DebbieMainWindow", "create_application", "main"]
