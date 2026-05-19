"""Pantalla de inicio de sesión."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.controllers.auth_controller import AuthController, AuthUser


class LoginDialog(QDialog):
    def __init__(self, auth_controller: AuthController) -> None:
        super().__init__()
        self.auth_controller = auth_controller
        self.authenticated_user: AuthUser | None = None

        self.setWindowTitle("Iniciar sesión - Sistema de facturación")
        self.setModal(True)
        self.setMinimumSize(460, 520)
        self.setObjectName("loginDialog")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        container = QWidget()
        container.setObjectName("loginBackground")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(42, 42, 42, 42)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("loginCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(34, 34, 34, 34)
        card_layout.setSpacing(16)

        title = QLabel("Sistema de facturación")
        title.setObjectName("loginTitle")
        subtitle = QLabel("Accede con tu usuario para continuar. Si Supabase no está configurado, entrarás en modo local.")
        subtitle.setObjectName("loginSubtitle")
        subtitle.setWordWrap(True)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email")
        self.email_input.setClearButtonEnabled(True)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Contraseña")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.error_label = QLabel("")
        self.error_label.setObjectName("loginError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        self.login_button = QPushButton("Iniciar sesión")
        self.login_button.clicked.connect(self.login)
        self.password_input.returnPressed.connect(self.login)
        self.email_input.returnPressed.connect(self.password_input.setFocus)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(8)
        card_layout.addWidget(self.email_input)
        card_layout.addWidget(self.password_input)
        card_layout.addWidget(self.error_label)
        card_layout.addWidget(self.login_button)

        container_layout.addWidget(card)
        root.addWidget(container)

        self.setStyleSheet(LOGIN_STYLESHEET)

    def login(self) -> None:
        self.error_label.hide()
        self.login_button.setEnabled(False)
        self.login_button.setText("Comprobando...")

        result = self.auth_controller.login(
            self.email_input.text(),
            self.password_input.text(),
        )

        self.login_button.setEnabled(True)
        self.login_button.setText("Iniciar sesión")

        if result.success and result.user is not None:
            self.authenticated_user = result.user
            self.accept()
            return

        self.error_label.setText(result.error or "No se pudo iniciar sesión.")
        self.error_label.show()


LOGIN_STYLESHEET = """
QDialog#loginDialog, QWidget#loginBackground {
    background: #f3f6fb;
    color: #111827;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 14px;
}

QFrame#loginCard {
    background: #ffffff;
    border: 1px solid #dfe4ec;
    border-radius: 10px;
    min-width: 340px;
    max-width: 380px;
}

QLabel {
    background: transparent;
}

QLabel#loginTitle {
    color: #111827;
    font-size: 25px;
    font-weight: 700;
}

QLabel#loginSubtitle {
    color: #5b6472;
}

QLabel#loginError {
    color: #b42318;
    background: #fff1f0;
    border: 1px solid #ffccc7;
    border-radius: 7px;
    padding: 10px;
}

QLineEdit {
    background: #ffffff;
    color: #111827;
    border: 1px solid #cfd6e2;
    border-radius: 7px;
    padding: 11px 12px;
    selection-background-color: #bfd7ff;
    selection-color: #111827;
}

QLineEdit:focus {
    border-color: #2563eb;
}

QLineEdit[placeholderText]:empty {
    color: #6b7280;
}

QPushButton {
    background: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 7px;
    padding: 11px 14px;
    font-weight: 700;
}

QPushButton:hover {
    background: #1d4ed8;
}

QPushButton:disabled {
    background: #aab7cc;
}
"""
