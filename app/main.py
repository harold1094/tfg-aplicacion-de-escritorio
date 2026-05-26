"""Punto de entrada de la aplicación."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QDialog

from app.services.auth_service import AuthService
from app.views.login_dialog import LoginDialog
from app.views.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    auth_service = AuthService()
    session = None
    if auth_service.is_configured():
        login = LoginDialog(auth_service)
        if login.exec() != QDialog.DialogCode.Accepted or login.session is None:
            return 0
        session = login.session

    window = MainWindow(session=session)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

