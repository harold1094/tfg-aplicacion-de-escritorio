"""Vista de productos y servicios."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.producto_controller import ProductoController
from app.models.security import UserPermissions
from app.views.producto_dialog import ProductoDialog


def _money(value: Decimal) -> str:
    return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


class ProductosView(QWidget):
    def __init__(self, controller: ProductoController, permissions: UserPermissions) -> None:
        super().__init__()
        self.controller = controller
        self.permissions = permissions
        self.rows = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Productos y servicios")
        title.setObjectName("viewTitle")
        subtitle = QLabel("Catálogo operativo para reutilizar conceptos al crear nuevas facturas.")
        subtitle.setObjectName("viewSubtitle")

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar producto o servicio")
        self.search_input.textChanged.connect(self.refresh_data)

        self.new_button = QPushButton("Nuevo")
        self.edit_button = QPushButton("Editar")
        self.delete_button = QPushButton("Eliminar")
        self.new_button.clicked.connect(self.create_producto)
        self.edit_button.clicked.connect(self.edit_selected_producto)
        self.delete_button.clicked.connect(self.delete_selected_producto)

        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(self.new_button)
        toolbar.addWidget(self.edit_button)
        toolbar.addWidget(self.delete_button)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Id", "Nombre", "Descripción", "Tipo", "Categoría", "Precio"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.itemDoubleClicked.connect(lambda _: self.edit_selected_producto())
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(toolbar)
        layout.addWidget(self.table)

        self.apply_permissions()
        self.refresh_data()

    def apply_permissions(self) -> None:
        enabled = self.permissions.can_manage_master_data
        self.new_button.setEnabled(enabled)
        self.edit_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)
        tooltip = "" if enabled else "Disponible solo para el rol administrador."
        self.new_button.setToolTip(tooltip)
        self.edit_button.setToolTip(tooltip)
        self.delete_button.setToolTip(tooltip)

    def refresh_data(self) -> None:
        query = self.search_input.text().strip().lower() if hasattr(self, "search_input") else ""
        self.rows = [
            producto
            for producto in self.controller.list_productos()
            if not query or query in producto.nombre.lower() or query in producto.descripcion.lower()
        ]

        self.table.setRowCount(len(self.rows))
        for row_index, producto in enumerate(self.rows):
            values = [producto.id, producto.nombre, producto.descripcion, producto.tipo, producto.categoria, _money(producto.precio)]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 5:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row_index, column, item)
        self.table.setColumnHidden(0, True)

    def current_producto_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.rows):
            return None
        return self.rows[row].id

    def create_producto(self) -> None:
        dialog = ProductoDialog(categories=self.controller.list_categories())
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        try:
            self.controller.create_producto(dialog.get_payload())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.refresh_data()

    def edit_selected_producto(self) -> None:
        producto_id = self.current_producto_id()
        if producto_id is None:
            return
        producto = self.controller.get_producto(producto_id)
        if producto is None:
            return

        dialog = ProductoDialog(producto, categories=self.controller.list_categories())
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        try:
            self.controller.update_producto(producto_id, dialog.get_payload())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.refresh_data()

    def delete_selected_producto(self) -> None:
        producto_id = self.current_producto_id()
        if producto_id is None:
            return
        if QMessageBox.question(self, "Confirmar", "¿Eliminar el producto seleccionado?") != QMessageBox.StandardButton.Yes:
            return

        try:
            self.controller.delete_producto(producto_id)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.refresh_data()
