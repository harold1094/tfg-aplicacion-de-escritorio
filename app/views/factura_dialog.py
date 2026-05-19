"""Diálogo de alta y edición de factura."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from app.models.cliente import Cliente
from app.models.factura import EstadoFactura, Factura, LineaFactura


class FacturaDialog(QDialog):
    def __init__(
        self,
        clientes: list[Cliente],
        categories: list[str],
        projects: list[str],
        factura: Factura | None = None,
    ) -> None:
        super().__init__()
        self.clientes = clientes
        self.factura = factura

        self.setWindowTitle("Factura")
        self.resize(860, 640)

        layout = QVBoxLayout(self)
        header = QGridLayout()

        self.numero_input = QLineEdit(factura.numero if factura else "")
        self.cliente_input = QComboBox()
        self.cliente_input.setEditable(False)
        for cliente in clientes:
            self.cliente_input.addItem(f"{cliente.nombre} ({cliente.email or 'sin email'})", cliente.id)
        if factura:
            index = self.cliente_input.findData(factura.cliente_id)
            if index >= 0:
                self.cliente_input.setCurrentIndex(index)

        self.fecha_input = QDateEdit()
        self.fecha_input.setCalendarPopup(True)
        self.fecha_input.setDate(_to_qdate(factura.fecha if factura else date.today()))

        self.vencimiento_input = QDateEdit()
        self.vencimiento_input.setCalendarPopup(True)
        self.vencimiento_input.setDate(_to_qdate(factura.fecha_vencimiento or factura.fecha if factura else date.today()))

        self.estado_input = QComboBox()
        self.estado_input.addItems([state.value for state in EstadoFactura])
        if factura:
            self.estado_input.setCurrentText(factura.estado.value)

        self.categoria_input = QComboBox()
        self.categoria_input.setEditable(True)
        self.categoria_input.addItems(categories)
        if factura and factura.categoria:
            self.categoria_input.setCurrentText(factura.categoria)

        self.proyecto_input = QComboBox()
        self.proyecto_input.setEditable(True)
        self.proyecto_input.addItems(projects)
        if factura and factura.proyecto:
            self.proyecto_input.setCurrentText(factura.proyecto)

        self.pagado_input = QLineEdit(str(factura.importe_pagado if factura else "0.00"))
        self.observaciones_input = QTextEdit(factura.observaciones if factura else "")
        self.observaciones_input.setFixedHeight(90)

        header.addWidget(QLabel("Número"), 0, 0)
        header.addWidget(self.numero_input, 0, 1)
        header.addWidget(QLabel("Cliente"), 0, 2)
        header.addWidget(self.cliente_input, 0, 3)
        header.addWidget(QLabel("Fecha"), 1, 0)
        header.addWidget(self.fecha_input, 1, 1)
        header.addWidget(QLabel("Vencimiento"), 1, 2)
        header.addWidget(self.vencimiento_input, 1, 3)
        header.addWidget(QLabel("Estado"), 2, 0)
        header.addWidget(self.estado_input, 2, 1)
        header.addWidget(QLabel("Categoría"), 2, 2)
        header.addWidget(self.categoria_input, 2, 3)
        header.addWidget(QLabel("Proyecto"), 3, 0)
        header.addWidget(self.proyecto_input, 3, 1)
        header.addWidget(QLabel("Importe pagado"), 3, 2)
        header.addWidget(self.pagado_input, 3, 3)

        lines_header = QHBoxLayout()
        lines_title = QLabel("Líneas de factura")
        lines_title.setObjectName("sectionTitle")
        add_line_button = QPushButton("Añadir línea")
        remove_line_button = QPushButton("Eliminar línea")
        add_line_button.clicked.connect(self.add_line)
        remove_line_button.clicked.connect(self.remove_selected_line)

        lines_header.addWidget(lines_title)
        lines_header.addStretch(1)
        lines_header.addWidget(add_line_button)
        lines_header.addWidget(remove_line_button)

        self.lines_table = QTableWidget(0, 4)
        self.lines_table.setHorizontalHeaderLabels(["Descripción", "Cantidad", "Precio unitario", "IVA"])
        self.lines_table.horizontalHeader().setStretchLastSection(False)
        self.lines_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.lines_table.setMinimumHeight(220)

        if factura and factura.lineas:
            for linea in factura.lineas:
                self.add_line(linea)
        else:
            self.add_line()

        form = QFormLayout()
        form.addRow("Observaciones", self.observaciones_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(header)
        layout.addLayout(lines_header)
        layout.addWidget(self.lines_table)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def add_line(self, line: LineaFactura | None = None) -> None:
        row = self.lines_table.rowCount()
        self.lines_table.insertRow(row)
        defaults = line or LineaFactura("Nuevo concepto", Decimal("1"), Decimal("0.00"), Decimal("0.21"))
        values = [
            defaults.descripcion,
            str(defaults.cantidad),
            str(defaults.precio_unitario),
            str(defaults.iva),
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column > 0:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.lines_table.setItem(row, column, item)

    def remove_selected_line(self) -> None:
        row = self.lines_table.currentRow()
        if row >= 0:
            self.lines_table.removeRow(row)

    def accept(self) -> None:
        if self.cliente_input.currentIndex() < 0:
            QMessageBox.warning(self, "Validación", "Selecciona un cliente.")
            return
        try:
            self.get_payload()
        except ValueError as exc:
            QMessageBox.warning(self, "Validación", str(exc))
            return
        super().accept()

    def get_payload(self) -> dict[str, object]:
        cliente = self.clientes[self.cliente_input.currentIndex()]
        lineas: list[dict[str, object]] = []
        for row in range(self.lines_table.rowCount()):
            descripcion = self._item_text(row, 0).strip()
            if not descripcion:
                continue
            lineas.append(
                {
                    "descripcion": descripcion,
                    "cantidad": Decimal(self._item_text(row, 1) or "1"),
                    "precio_unitario": Decimal(self._item_text(row, 2) or "0"),
                    "iva": Decimal(self._item_text(row, 3) or "0.21"),
                }
            )

        if not lineas:
            raise ValueError("La factura debe tener al menos una línea.")

        return {
            "numero": self.numero_input.text().strip(),
            "cliente_id": cliente.id,
            "cliente_nombre": cliente.nombre,
            "cliente_email": cliente.email,
            "fecha": self.fecha_input.date().toPython(),
            "fecha_vencimiento": self.vencimiento_input.date().toPython(),
            "estado": self.estado_input.currentText(),
            "categoria": self.categoria_input.currentText().strip(),
            "proyecto": self.proyecto_input.currentText().strip(),
            "importe_pagado": Decimal(self.pagado_input.text().strip() or "0.00"),
            "observaciones": self.observaciones_input.toPlainText().strip(),
            "lineas": lineas,
        }

    def _item_text(self, row: int, column: int) -> str:
        item = self.lines_table.item(row, column)
        return item.text() if item is not None else ""


def _to_qdate(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)
