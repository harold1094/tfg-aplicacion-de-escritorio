"""Punto de entrada de la aplicación."""

from __future__ import annotations

import sys
import os

# Asegurar que el directorio raíz del proyecto esté en sys.path para entornos de Python portable
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app.services.auth_service import AuthService
from app.views.login_dialog import LoginDialog
from app.views.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    auth_service = AuthService()
    if not auth_service.is_configured():
        QMessageBox.critical(
            None,
            "Supabase no configurado",
            "Debes configurar SUPABASE_URL y SUPABASE_KEY en el archivo .env para iniciar sesion.",
        )
        return 1

    login = LoginDialog(auth_service)
    if login.exec() != QDialog.DialogCode.Accepted or login.session is None:
        return 0
    session = login.session

    window = MainWindow(session=session)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

