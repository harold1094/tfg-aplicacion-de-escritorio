"""Ventana principal de la aplicación."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.controllers.audit_controller import AuditController
from app.controllers.auth_controller import AuthController, AuthUser
from app.controllers.cliente_controller import ClienteController
from app.controllers.factura_controller import FacturaController
from app.controllers.producto_controller import ProductoController
from app.models.security import UserRole, permissions_for_role
from app.services.audit_service import AuditService
from app.services.email_service import EmailService
from app.services.local_store import LocalStore
from app.views.audit_view import AuditView
from app.views.clientes_view import ClientesView
from app.views.dashboard_view import DashboardView
from app.views.facturas_view import FacturasView
from app.views.productos_view import ProductosView


class MainWindow(QMainWindow):
    def __init__(self, auth_controller: AuthController | None = None, authenticated_user: AuthUser | None = None) -> None:
        super().__init__()
        self.auth_controller = auth_controller
        self.authenticated_user = authenticated_user
        self.permissions = (
            authenticated_user.permissions
            if authenticated_user is not None
            else permissions_for_role(UserRole.ADMINISTRADOR)
        )
        self.setWindowTitle("Sistema de facturación - Escritorio Qt")
        self.resize(1320, 820)
        self.setMinimumSize(1080, 720)

        self.store = LocalStore()
        self.audit_service = AuditService(self.store)
        self.email_service = EmailService()

        self.cliente_controller = ClienteController(
            store=self.store,
            audit_service=self.audit_service,
            current_user=authenticated_user.email if authenticated_user else "sistema",
        )
        self.producto_controller = ProductoController(
            store=self.store,
            audit_service=self.audit_service,
            current_user=authenticated_user.email if authenticated_user else "sistema",
        )
        self.factura_controller = FacturaController(
            store=self.store,
            audit_service=self.audit_service,
            current_user=authenticated_user.email if authenticated_user else "sistema",
        )
        self.audit_controller = AuditController(self.audit_service)

        central = QWidget()
        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 22, 18, 22)
        sidebar_layout.setSpacing(18)

        app_title = QLabel("Facturación")
        app_title.setObjectName("appTitle")
        app_subtitle = QLabel("Aplicación de escritorio Qt")
        app_subtitle.setObjectName("appSubtitle")

        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.setFocusPolicy(Qt.NoFocus)
        self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.navigation.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.navigation.setFixedHeight(320)

        for label in ["Dashboard", "Clientes", "Productos/Servicios", "Facturas", "Actividad"]:
            self.navigation.addItem(QListWidgetItem(label))

        sidebar_layout.addWidget(app_title)
        sidebar_layout.addWidget(app_subtitle)
        sidebar_layout.addWidget(self.navigation)
        sidebar_layout.addStretch(1)

        session_text = "Sesión iniciada"
        if authenticated_user is not None:
            session_text = f"Sesión: {authenticated_user.email}\nRol: {authenticated_user.role.value}"
        session_label = QLabel(session_text)
        session_label.setObjectName("sidebarFooter")
        session_label.setWordWrap(True)

        logout_button = QPushButton("Cerrar sesión")
        logout_button.setObjectName("logoutButton")
        logout_button.clicked.connect(self.logout)

        mode = "Supabase conectado" if self.factura_controller.supabase is not None else "Modo operativo local"
        footer = QLabel(mode)
        footer.setObjectName("sidebarFooter")
        footer.setWordWrap(True)
        sidebar_layout.addWidget(session_label)
        sidebar_layout.addWidget(logout_button)
        sidebar_layout.addWidget(footer)

        self.stack = QStackedWidget()
        self.dashboard_view = DashboardView(self.factura_controller, self.cliente_controller, self.producto_controller)
        self.clientes_view = ClientesView(self.cliente_controller, self.permissions)
        self.productos_view = ProductosView(self.producto_controller, self.permissions)
        self.facturas_view = FacturasView(
            self.factura_controller,
            self.cliente_controller,
            self.producto_controller,
            permissions=self.permissions,
            email_service=self.email_service,
        )
        self.audit_view = AuditView(self.audit_controller)

        self.stack.addWidget(self.dashboard_view)
        self.stack.addWidget(self.clientes_view)
        self.stack.addWidget(self.productos_view)
        self.stack.addWidget(self.facturas_view)
        self.stack.addWidget(self.audit_view)
        if self.permissions is not None and not self.permissions.can_view_audit:
            self.navigation.item(4).setHidden(True)

        shell.addWidget(sidebar)
        shell.addWidget(self.stack, 1)

        self.navigation.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.navigation.currentRowChanged.connect(self._refresh_current_view)
        self.navigation.setCurrentRow(0)
        self.setCentralWidget(central)
        self.setStyleSheet(APP_STYLESHEET)

    def logout(self) -> None:
        if self.auth_controller is not None:
            self.auth_controller.logout()
        self.close()

    def _refresh_current_view(self, *_args) -> None:
        self.dashboard_view.refresh_data()
        self.clientes_view.refresh_data()
        self.productos_view.refresh_data()
        self.facturas_view.refresh_data()
        self.audit_view.refresh_data()


APP_STYLESHEET = """
QMainWindow, QWidget {
    background: #f5f7fb;
    color: #111827;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 14px;
}

QLabel {
    background: transparent;
}

QFrame#sidebar {
    background: #101827;
    min-width: 280px;
    max-width: 280px;
}

QLabel#appTitle {
    color: #ffffff;
    font-size: 25px;
    font-weight: 700;
    padding: 0;
}

QLabel#appSubtitle, QLabel#sidebarFooter {
    color: #9ca3af;
    padding: 0;
}

QListWidget#navigation {
    background: transparent;
    border: none;
    color: #d1d5db;
    outline: none;
}

QListWidget#navigation::item {
    padding: 14px 16px;
    border-radius: 8px;
    margin: 4px 0;
}

QListWidget#navigation::item:selected {
    background: #2563eb;
    color: #ffffff;
}

QListWidget#navigation::item:hover {
    background: #1f2937;
}

QLabel#viewTitle {
    color: #111827;
    font-size: 28px;
    font-weight: 700;
}

QLabel#viewSubtitle {
    color: #4b5563;
}

QLabel#sectionTitle {
    color: #111827;
    font-size: 18px;
    font-weight: 700;
}

QFrame#metricCard {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
}

QLabel#metricTitle {
    color: #6b7280;
    font-size: 13px;
    padding: 0;
}

QLabel#metricValue {
    color: #111827;
    font-size: 24px;
    font-weight: 700;
    padding: 0;
}

QLineEdit, QComboBox, QTextEdit, QDateEdit {
    background: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 7px;
    padding: 9px 11px;
}

QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QDateEdit:focus {
    border-color: #2563eb;
}

QPushButton {
    background: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 7px;
    padding: 9px 14px;
    font-weight: 600;
}

QPushButton:hover {
    background: #1d4ed8;
}

QPushButton:disabled {
    background: #d1d5db;
    color: #6b7280;
}

QPushButton#logoutButton {
    background: #1f2937;
    color: #e5e7eb;
    text-align: left;
}

QPushButton#logoutButton:hover {
    background: #374151;
}

QTableWidget, QListWidget, QTabWidget::pane {
    background: #ffffff;
    alternate-background-color: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    gridline-color: #e5e7eb;
    selection-background-color: #dbeafe;
    selection-color: #111827;
}

QHeaderView::section {
    background: #eef2f7;
    color: #374151;
    border: none;
    border-bottom: 1px solid #d1d5db;
    padding: 10px 12px;
    font-weight: 700;
}
"""
