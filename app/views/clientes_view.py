"""Vista de clientes."""

from __future__ import annotations

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

from app.controllers.cliente_controller import ClienteController


class ClientesView(QWidget):
    def __init__(self, controller: ClienteController) -> None:
        super().__init__()
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Clientes")
        title.setObjectName("viewTitle")
        subtitle = QLabel("Consulta inicial de clientes. Las altas se activarán cuando el esquema de Supabase esté validado.")
        subtitle.setObjectName("viewSubtitle")

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar cliente")
        self.search_input.textChanged.connect(self.refresh_data)

        new_button = QPushButton("Nuevo cliente")
        new_button.setEnabled(False)
        new_button.setToolTip("Pendiente de validar tablas y columnas reales de Supabase")

        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(new_button)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Nombre", "Email", "Teléfono", "NIF", "Dirección"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        header = self.table.horizontalHeader()
        header.setMinimumSectionSize(110)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(toolbar)
        layout.addWidget(self.table)

        self.refresh_data()

    def refresh_data(self) -> None:
        query = self.search_input.text().strip().lower() if hasattr(self, "search_input") else ""
        clientes = [
            cliente
            for cliente in self.controller.list_clientes()
            if not query or query in cliente.nombre.lower() or query in cliente.email.lower()
        ]

        self.table.setRowCount(len(clientes))
        for row_index, cliente in enumerate(clientes):
            values = [cliente.nombre, cliente.email, cliente.telefono, cliente.nif, cliente.direccion]
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, QTableWidgetItem(value))

        self.table.setColumnWidth(2, 130)
        self.table.setColumnWidth(3, 130)
