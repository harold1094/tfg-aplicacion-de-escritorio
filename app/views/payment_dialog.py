"""Diálogo para registrar cobros."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QMessageBox,
    QVBoxLayout,
)


class PaymentDialog(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Registrar cobro")
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.amount_input = QDoubleSpinBox()
        self.amount_input.setDecimals(2)
        self.amount_input.setMaximum(1_000_000)
        self.amount_input.setValue(0.00)

        form.addRow("Importe", self.amount_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(buttons)

    def accept(self) -> None:
        if self.amount_input.value() <= 0:
            QMessageBox.warning(self, "Validación", "El importe debe ser mayor que cero.")
            return
        super().accept()

    def amount(self) -> Decimal:
        return Decimal(str(self.amount_input.value()))
