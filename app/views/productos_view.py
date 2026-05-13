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
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.producto_controller import ProductoController


def _money(value: Decimal) -> str:
    return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


class ProductosView(QWidget):
    def __init__(self, controller: ProductoController) -> None:
        super().__init__()
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Productos y servicios")
        title.setObjectName("viewTitle")
        subtitle = QLabel("Catálogo preparado para añadir líneas directamente a facturas en la siguiente fase.")
        subtitle.setObjectName("viewSubtitle")

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar producto o servicio")
        self.search_input.textChanged.connect(self.refresh_data)

        new_button = QPushButton("Nuevo producto/servicio")
        new_button.setEnabled(False)
        new_button.setToolTip("Pendiente de validar tablas y columnas reales de Supabase")

        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(new_button)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nombre", "Descripción", "Tipo", "Precio"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        header = self.table.horizontalHeader()
        header.setMinimumSectionSize(120)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(toolbar)
        layout.addWidget(self.table)

        self.refresh_data()

    def refresh_data(self) -> None:
        query = self.search_input.text().strip().lower() if hasattr(self, "search_input") else ""
        productos = [
            producto
            for producto in self.controller.list_productos()
            if not query or query in producto.nombre.lower() or query in producto.descripcion.lower()
        ]

        self.table.setRowCount(len(productos))
        for row_index, producto in enumerate(productos):
            values = [producto.nombre, producto.descripcion, producto.tipo, _money(producto.precio)]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 3:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row_index, column, item)

        self.table.setColumnWidth(2, 140)
        self.table.setColumnWidth(3, 120)
