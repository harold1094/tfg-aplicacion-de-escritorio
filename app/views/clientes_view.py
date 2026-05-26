"""Vista de clientes."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
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
        self._card_columns = 3

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

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

        self.cards_grid = QGridLayout()
        self.cards_grid.setHorizontalSpacing(16)
        self.cards_grid.setVerticalSpacing(16)

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
        layout.addLayout(self.cards_grid)
        self.table.hide()

        self.refresh_data()

    def refresh_data(self) -> None:
        query = self.search_input.text().strip().lower() if hasattr(self, "search_input") else ""
        clientes = [
            cliente
            for cliente in self.controller.list_clientes()
            if not query or query in cliente.nombre.lower() or query in cliente.email.lower()
        ]

        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        columns = self._grid_columns()
        for index, cliente in enumerate(clientes):
            nombre = self._display(cliente.nombre, "Cliente sin nombre")
            email = self._display(cliente.email)
            telefono = self._display(cliente.telefono)
            nif = self._display(cliente.nif)
            direccion = self._display(cliente.direccion)
            card = QFrame()
            card.setObjectName("clientCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 18, 18, 18)
            card_layout.setSpacing(12)

            top = QHBoxLayout()
            top.setSpacing(12)
            initials = "".join(part[:1] for part in nombre.split()[:2]).upper() or "CL"
            avatar = QLabel(initials)
            avatar.setObjectName("clientAvatar")
            name = QLabel(nombre)
            name.setObjectName("clientName")
            name.setWordWrap(True)
            nif_label = QLabel(nif)
            nif_label.setObjectName("clientMeta")
            name_block = QVBoxLayout()
            name_block.setSpacing(4)
            name_block.addWidget(name)
            name_block.addWidget(nif_label)
            top.addWidget(avatar)
            top.addLayout(name_block, 1)
            arrow = QLabel(">")
            arrow.setObjectName("clientArrow")
            top.addWidget(arrow, 0)
            card_layout.addLayout(top)

            email_label = QLabel(f"✉  {email}")
            email_label.setObjectName("clientDetail")
            email_label.setWordWrap(True)
            phone_label = QLabel(f"☎  {telefono}")
            phone_label.setObjectName("clientDetail")
            address_label = QLabel(f"⌖  {direccion}")
            address_label.setObjectName("clientDetail")
            address_label.setWordWrap(True)
            card_layout.addWidget(email_label)
            card_layout.addWidget(phone_label)
            card_layout.addWidget(address_label)
            card_layout.addStretch(1)

            divider = QFrame()
            divider.setObjectName("clientDivider")
            card_layout.addWidget(divider)

            footer = QHBoxLayout()
            footer.setSpacing(12)
            billed = QLabel("Facturado\n0,00 €")
            billed.setObjectName("clientFooter")
            invoices = QLabel("Facturas\n0")
            invoices.setObjectName("clientFooter")
            footer.addWidget(billed)
            footer.addStretch(1)
            footer.addWidget(invoices)
            card_layout.addLayout(footer)

            self.cards_grid.addWidget(card, index // columns, index % columns)

        self.table.setRowCount(len(clientes))
        for row_index, cliente in enumerate(clientes):
            values = [cliente.nombre, cliente.email, cliente.telefono, cliente.nif, cliente.direccion]
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, QTableWidgetItem(value))

        self.table.setColumnWidth(2, 130)
        self.table.setColumnWidth(3, 130)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        columns = self._grid_columns()
        if columns != self._card_columns:
            self._card_columns = columns
            self.refresh_data()

    def _grid_columns(self) -> int:
        return 2 if self.width() < 1350 else 3

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
