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
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.controllers.cliente_controller import ClienteController
from app.controllers.factura_controller import FacturaController
from app.controllers.producto_controller import ProductoController
from app.views.clientes_view import ClientesView
from app.views.dashboard_view import DashboardView
from app.views.facturas_view import FacturasView
from app.views.productos_view import ProductosView


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sistema de facturación - Escritorio")
        self.resize(1180, 740)
        self.setMinimumSize(980, 620)

        self.cliente_controller = ClienteController()
        self.producto_controller = ProductoController()
        self.factura_controller = FacturaController()

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
        app_subtitle = QLabel("Módulo escritorio TFG")
        app_subtitle.setObjectName("appSubtitle")

        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.setFocusPolicy(Qt.NoFocus)

        for label in ["Dashboard", "Clientes", "Productos/Servicios", "Facturas"]:
            self.navigation.addItem(QListWidgetItem(label))

        sidebar_layout.addWidget(app_title)
        sidebar_layout.addWidget(app_subtitle)
        sidebar_layout.addWidget(self.navigation)
        sidebar_layout.addStretch(1)

        footer = QLabel("Modo seguro: solo lectura")
        footer.setObjectName("sidebarFooter")
        sidebar_layout.addWidget(footer)

        self.stack = QStackedWidget()
        self.stack.addWidget(
            DashboardView(self.factura_controller, self.cliente_controller, self.producto_controller)
        )
        self.stack.addWidget(ClientesView(self.cliente_controller))
        self.stack.addWidget(ProductosView(self.producto_controller))
        self.stack.addWidget(FacturasView(self.factura_controller))

        shell.addWidget(sidebar)
        shell.addWidget(self.stack, 1)

        self.navigation.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        self.setCentralWidget(central)
        self.setStyleSheet(APP_STYLESHEET)


APP_STYLESHEET = """
QMainWindow, QWidget {
    background: #f5f7fb;
    color: #111827;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 14px;
}

QFrame#sidebar {
    background: #111827;
    min-width: 245px;
    max-width: 245px;
}

QLabel#appTitle {
    color: #ffffff;
    font-size: 24px;
    font-weight: 700;
}

QLabel#appSubtitle, QLabel#sidebarFooter {
    color: #9ca3af;
}

QListWidget#navigation {
    background: transparent;
    border: none;
    color: #d1d5db;
    outline: none;
}

QListWidget#navigation::item {
    padding: 12px 14px;
    border-radius: 8px;
    margin: 3px 0;
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
}

QLabel#metricValue {
    color: #111827;
    font-size: 24px;
    font-weight: 700;
}

QLineEdit {
    background: #ffffff;
    border: 1px solid #d1d5db;
    border-radius: 7px;
    padding: 9px 11px;
}

QLineEdit:focus {
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

QTableWidget {
    background: #ffffff;
    alternate-background-color: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    gridline-color: #e5e7eb;
}

QHeaderView::section {
    background: #eef2f7;
    color: #374151;
    border: none;
    border-bottom: 1px solid #d1d5db;
    padding: 9px;
    font-weight: 700;
}
"""

