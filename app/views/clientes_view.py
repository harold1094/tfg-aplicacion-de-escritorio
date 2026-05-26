"""Vista de clientes."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
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
from app.models.cliente import Cliente


class ClienteDialog(QDialog):
    def __init__(self, parent: QWidget, cliente: Cliente | None = None) -> None:
        super().__init__(parent)
        self.cliente = cliente
        self.setWindowTitle("Editar cliente" if cliente else "Nuevo cliente")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.nombre_input = QLineEdit(cliente.nombre if cliente else "")
        self.email_input = QLineEdit(cliente.email if cliente else "")
        self.telefono_input = QLineEdit(cliente.telefono if cliente else "")
        self.nif_input = QLineEdit(cliente.nif if cliente else "")
        self.direccion_input = QLineEdit(cliente.direccion if cliente else "")
        form.addRow("Nombre", self.nombre_input)
        form.addRow("Email", self.email_input)
        form.addRow("Telefono", self.telefono_input)
        form.addRow("NIF/CIF", self.nif_input)
        form.addRow("Direccion", self.direccion_input)
        layout.addLayout(form)

        actions = QHBoxLayout()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Guardar")
        save.clicked.connect(self.accept)
        actions.addStretch(1)
        actions.addWidget(cancel)
        actions.addWidget(save)
        layout.addLayout(actions)

    def build_cliente(self) -> Cliente:
        return Cliente(
            id=self.cliente.id if self.cliente else "",
            nombre=self.nombre_input.text().strip(),
            email=self.email_input.text().strip(),
            telefono=self.telefono_input.text().strip(),
            nif=self.nif_input.text().strip(),
            direccion=self.direccion_input.text().strip(),
        )


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
        new_button.clicked.connect(self.new_cliente)

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
        self.table.cellDoubleClicked.connect(self.edit_cliente)
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

    def current_clientes(self) -> list[Cliente]:
        query = self.search_input.text().strip().lower() if hasattr(self, "search_input") else ""
        return [
            cliente
            for cliente in self.controller.list_clientes()
            if not query or query in cliente.nombre.lower() or query in cliente.email.lower()
        ]

    def new_cliente(self) -> None:
        dialog = ClienteDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        cliente = dialog.build_cliente()
        if not cliente.nombre:
            QMessageBox.warning(self, "Faltan datos", "El nombre del cliente es obligatorio.")
            return
        try:
            self.controller.create_cliente(cliente)
        except Exception as exc:
            QMessageBox.warning(self, "No se pudo guardar", str(exc))
            return
        self.refresh_data()

    def edit_cliente(self, row: int, _column: int) -> None:
        clientes = self.current_clientes()
        if row >= len(clientes):
            return
        dialog = ClienteDialog(self, clientes[row])
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        cliente = dialog.build_cliente()
        try:
            self.controller.update_cliente(cliente)
        except Exception as exc:
            QMessageBox.warning(self, "No se pudo actualizar", str(exc))
            return
        self.refresh_data()
