"""Vista de clientes."""

from __future__ import annotations

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

from app.controllers.cliente_controller import ClienteController
from app.models.security import UserPermissions
from app.views.cliente_dialog import ClienteDialog


class ClientesView(QWidget):
    def __init__(self, controller: ClienteController, permissions: UserPermissions) -> None:
        super().__init__()
        self.controller = controller
        self.permissions = permissions
        self.rows = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Clientes")
        title.setObjectName("viewTitle")
        subtitle = QLabel("Gestión operativa de clientes con búsqueda, alta, edición y baja.")
        subtitle.setObjectName("viewSubtitle")

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar cliente")
        self.search_input.textChanged.connect(self.refresh_data)

        self.new_button = QPushButton("Nuevo cliente")
        self.edit_button = QPushButton("Editar")
        self.delete_button = QPushButton("Eliminar")
        self.new_button.clicked.connect(self.create_cliente)
        self.edit_button.clicked.connect(self.edit_selected_cliente)
        self.delete_button.clicked.connect(self.delete_selected_cliente)

        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(self.new_button)
        toolbar.addWidget(self.edit_button)
        toolbar.addWidget(self.delete_button)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Id", "Nombre", "Email", "Teléfono", "NIF", "Dirección"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.itemDoubleClicked.connect(lambda _: self.edit_selected_cliente())
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

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
            cliente
            for cliente in self.controller.list_clientes()
            if not query or query in cliente.nombre.lower() or query in cliente.email.lower()
        ]

        self.table.setRowCount(len(self.rows))
        for row_index, cliente in enumerate(self.rows):
            values = [cliente.id, cliente.nombre, cliente.email, cliente.telefono, cliente.nif, cliente.direccion]
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, QTableWidgetItem(value))
        self.table.setColumnHidden(0, True)

    def current_cliente_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.rows):
            return None
        return self.rows[row].id

    def create_cliente(self) -> None:
        dialog = ClienteDialog()
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        try:
            self.controller.create_cliente(dialog.get_payload())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.refresh_data()

    def edit_selected_cliente(self) -> None:
        cliente_id = self.current_cliente_id()
        if cliente_id is None:
            return
        cliente = self.controller.get_cliente(cliente_id)
        if cliente is None:
            return

        dialog = ClienteDialog(cliente)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        try:
            self.controller.update_cliente(cliente_id, dialog.get_payload())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.refresh_data()

    def delete_selected_cliente(self) -> None:
        cliente_id = self.current_cliente_id()
        if cliente_id is None:
            return
        if QMessageBox.question(self, "Confirmar", "¿Eliminar el cliente seleccionado?") != QMessageBox.StandardButton.Yes:
            return

        try:
            self.controller.delete_cliente(cliente_id)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.refresh_data()
