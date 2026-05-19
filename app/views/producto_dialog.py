"""Diálogo de producto o servicio."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from app.models.producto import Producto


class ProductoDialog(QDialog):
    def __init__(self, producto: Producto | None = None, categories: list[str] | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Producto o servicio")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.nombre_input = QLineEdit(producto.nombre if producto else "")
        self.descripcion_input = QTextEdit(producto.descripcion if producto else "")
        self.descripcion_input.setFixedHeight(100)
        self.precio_input = QDoubleSpinBox()
        self.precio_input.setDecimals(2)
        self.precio_input.setMaximum(1_000_000)
        self.precio_input.setValue(float(producto.precio if producto else Decimal("0.00")))
        self.tipo_input = QComboBox()
        self.tipo_input.addItems(["PRODUCTO", "SERVICIO"])
        if producto:
            self.tipo_input.setCurrentText(producto.tipo)
        self.categoria_input = QComboBox()
        self.categoria_input.setEditable(True)
        self.categoria_input.addItems(categories or [])
        if producto and producto.categoria:
            self.categoria_input.setCurrentText(producto.categoria)
        self.activo_input = QCheckBox("Elemento activo")
        self.activo_input.setChecked(producto.activo if producto else True)

        form.addRow("Nombre", self.nombre_input)
        form.addRow("Descripción", self.descripcion_input)
        form.addRow("Precio", self.precio_input)
        form.addRow("Tipo", self.tipo_input)
        form.addRow("Categoría", self.categoria_input)
        form.addRow("", self.activo_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(buttons)

    def accept(self) -> None:
        if not self.nombre_input.text().strip():
            QMessageBox.warning(self, "Validación", "El nombre del producto o servicio es obligatorio.")
            return
        super().accept()

    def get_payload(self) -> dict[str, object]:
        return {
            "nombre": self.nombre_input.text().strip(),
            "descripcion": self.descripcion_input.toPlainText().strip(),
            "precio": Decimal(str(self.precio_input.value())),
            "tipo": self.tipo_input.currentText(),
            "categoria": self.categoria_input.currentText().strip(),
            "activo": self.activo_input.isChecked(),
        }
