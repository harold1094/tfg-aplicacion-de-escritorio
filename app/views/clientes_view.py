"""Vista de clientes."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QFrame,
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

        toolbar_panel = QFrame()
        toolbar_panel.setObjectName("clientsToolbar")
        toolbar = QHBoxLayout(toolbar_panel)
        toolbar.setContentsMargins(14, 14, 14, 14)
        toolbar.setSpacing(12)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("clientsSearch")
        self.search_input.setPlaceholderText("Buscar por cliente, NIF, email o telefono")
        self.search_input.textChanged.connect(self.refresh_data)

        new_button = QPushButton("Nuevo cliente")
        new_button.setObjectName("primaryButton")
        new_button.clicked.connect(self.new_cliente)

        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(new_button)

        self.table = QTableWidget(0, 6)
        self.table.setObjectName("clientsTable")
        self.table.setHorizontalHeaderLabels(["Cliente", "NIF/CIF", "Email", "Telefono", "Direccion", "Editar"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setMinimumHeight(420)
        self.table.cellDoubleClicked.connect(self.edit_cliente)
        header = self.table.horizontalHeader()
        header.setMinimumSectionSize(90)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        self.empty_state = QLabel("No hay clientes para mostrar.")
        self.empty_state.setObjectName("emptyState")
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state.setMinimumHeight(220)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(toolbar_panel)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.empty_state, 1)

        self.refresh_data()

    def refresh_data(self) -> None:
        clientes = self.current_clientes()

        self.table.setRowCount(len(clientes))
        for row_index, cliente in enumerate(clientes):
            values = [
                self._display(cliente.nombre, "Cliente sin nombre"),
                self._display(cliente.nif),
                self._display(cliente.email),
                self._display(cliente.telefono),
                self._display(cliente.direccion),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (1, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_index, column, item)
            edit_button = QPushButton("Editar")
            edit_button.setObjectName("rowEditButton")
            edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_button.clicked.connect(lambda _checked=False, row=row_index: self.edit_cliente(row, 0))
            self.table.setCellWidget(row_index, 5, edit_button)
            self.table.setRowHeight(row_index, 54)

        self.table.setColumnWidth(1, 130)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(5, 92)
        self.table.setVisible(bool(clientes))
        self.empty_state.setVisible(not clientes)
        if not clientes:
            query = self.search_input.text().strip() if hasattr(self, "search_input") else ""
            self.empty_state.setText("No hay clientes que coincidan con la busqueda." if query else "No hay clientes para mostrar.")

    @staticmethod
    def _display(value: str, fallback: str = "-") -> str:
        text = (value or "").strip()
        if not text or text.lower() == "none":
            return fallback
        return text

    def current_clientes(self) -> list[Cliente]:
        query = self.search_input.text().strip().lower() if hasattr(self, "search_input") else ""
        return [
            cliente
            for cliente in self.controller.list_clientes()
            if not query
            or query
            in " ".join(
                [
                    cliente.nombre,
                    cliente.email,
                    cliente.telefono,
                    cliente.nif,
                    cliente.direccion,
                ]
            ).lower()
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
