"""Punto de entrada de la aplicación."""

from __future__ import annotations

import sys
import os
from pathlib import Path
import ctypes

# Asegurar que el directorio raíz del proyecto esté en sys.path para entornos de Python portable
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app.services.auth_service import AuthService
from app.views.login_dialog import LoginDialog
from app.views.main_window import MainWindow


ASSETS_DIR = Path(__file__).resolve().parent / "assets"
BRAND_ICON_ICO_PATH = ASSETS_DIR / "automanize-1.ico"
BRAND_ICON_PNG_PATH = ASSETS_DIR / "automanize-1.png"
APP_USER_MODEL_ID = "Automanize.DesktopApp"


def _resolve_brand_icon_path() -> Path | None:
    if BRAND_ICON_ICO_PATH.exists():
        return BRAND_ICON_ICO_PATH
    if BRAND_ICON_PNG_PATH.exists():
        return BRAND_ICON_PNG_PATH
    return None


def _configure_windows_identity() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        return


def main() -> int:
    _configure_windows_identity()
    app = QApplication(sys.argv)
    app.setApplicationName("Automanize")
    app.setOrganizationName("Automanize")
    brand_icon_path = _resolve_brand_icon_path()
    if brand_icon_path is not None:
        app.setWindowIcon(QIcon(str(brand_icon_path)))
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

