"""Punto de entrada de la aplicación."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QDialog

from app.controllers.auth_controller import AuthController
from app.views.login_dialog import LoginDialog
from app.views.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)

    auth_controller = AuthController()
    login_dialog = LoginDialog(auth_controller)
    if login_dialog.exec() != QDialog.DialogCode.Accepted:
        return 0

    window = MainWindow(
        auth_controller=auth_controller,
        authenticated_user=login_dialog.authenticated_user,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
