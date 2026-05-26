"""Dialogo de login Supabase para escritorio."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.services.auth_service import AuthService, AuthSession


class LoginDialog(QDialog):
    def __init__(self, auth_service: AuthService, parent=None) -> None:
        super().__init__(parent)
        self.auth_service = auth_service
        self.session: AuthSession | None = None
        self.setWindowTitle("Iniciar sesion")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        title = QLabel("Facturacion")
        title.setObjectName("viewTitle")
        subtitle = QLabel("Acceso real contra Supabase. Si el usuario no existe o la contrasena es incorrecta, no entra.")
        subtitle.setObjectName("viewSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        form = QFormLayout()
        self.email_input = QLineEdit("")
        self.email_input.setPlaceholderText("correo@empresa.com")
        self.password_input = QLineEdit("")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Contrasena")
        form.addRow("Email", self.email_input)
        form.addRow("Contrasena", self.password_input)
        layout.addLayout(form)

        actions = QHBoxLayout()
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("ghostButton")
        cancel.clicked.connect(self.reject)
        login = QPushButton("Entrar")
        login.clicked.connect(self.login)
        actions.addWidget(cancel)
        actions.addStretch(1)
        actions.addWidget(login)
        layout.addLayout(actions)

    def login(self) -> None:
        try:
            self.session = self.auth_service.login(
                self.email_input.text().strip(),
                self.password_input.text(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "No se pudo iniciar sesion", str(exc))
            return
        self.accept()
