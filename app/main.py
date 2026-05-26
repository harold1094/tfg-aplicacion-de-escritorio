"""Punto de entrada de la aplicación."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QWidget

from app.services.auth_service import AuthService
from app.views.login_dialog import LoginDialog
from app.views.main_window import MainWindow


LOG_PATH = Path.cwd() / "desktop_startup_error.log"


def _write_error_log(exc: BaseException) -> Path:
    details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    LOG_PATH.write_text(details, encoding="utf-8")
    return LOG_PATH


def _center_and_focus(widget: QWidget) -> None:
    widget.adjustSize()
    window_handle = widget.windowHandle()
    screen = None
    if window_handle is not None:
        screen = window_handle.screen()
    if screen is None:
        screen = QGuiApplication.primaryScreen()
    if screen is not None:
        available = screen.availableGeometry()
        frame = widget.frameGeometry()
        frame.moveCenter(available.center())
        widget.move(frame.topLeft())
    widget.show()
    widget.raise_()
    widget.activateWindow()
    if window_handle is not None:
        window_handle.requestActivate()


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    auth_service = AuthService()
    session = None
    if auth_service.is_configured():
        login = LoginDialog(auth_service)
        login.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        _center_and_focus(login)
        if login.exec() != QDialog.DialogCode.Accepted or login.session is None:
            return 0
        session = login.session

    try:
        window = MainWindow(session=session)
    except Exception as exc:
        log_path = _write_error_log(exc)
        QMessageBox.critical(
            None,
            "Error al iniciar la aplicación",
            f"La ventana principal no se ha podido abrir.\n\n{exc}\n\nSe ha guardado un log en:\n{log_path}",
        )
        return 1
    _center_and_focus(window)
    return app.exec()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        log_path = _write_error_log(exc)
        print(f"Error al iniciar la aplicación. Revisa el log: {log_path}", file=sys.stderr)
        raise

