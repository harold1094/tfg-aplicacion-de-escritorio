"""Diálogo de cliente."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from app.models.cliente import Cliente


class ClienteDialog(QDialog):
    def __init__(self, cliente: Cliente | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Cliente")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.nombre_input = QLineEdit(cliente.nombre if cliente else "")
        self.email_input = QLineEdit(cliente.email if cliente else "")
        self.telefono_input = QLineEdit(cliente.telefono if cliente else "")
        self.nif_input = QLineEdit(cliente.nif if cliente else "")
        self.direccion_input = QLineEdit(cliente.direccion if cliente else "")
        self.activo_input = QCheckBox("Cliente activo")
        self.activo_input.setChecked(cliente.activo if cliente else True)

        form.addRow("Nombre", self.nombre_input)
        form.addRow("Email", self.email_input)
        form.addRow("Teléfono", self.telefono_input)
        form.addRow("NIF", self.nif_input)
        form.addRow("Dirección", self.direccion_input)
        form.addRow("", self.activo_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(buttons)

    def accept(self) -> None:
        if not self.nombre_input.text().strip():
            QMessageBox.warning(self, "Validación", "El nombre del cliente es obligatorio.")
            return
        super().accept()

    def get_payload(self) -> dict[str, object]:
        return {
            "nombre": self.nombre_input.text().strip(),
            "email": self.email_input.text().strip(),
            "telefono": self.telefono_input.text().strip(),
            "nif": self.nif_input.text().strip(),
            "direccion": self.direccion_input.text().strip(),
            "activo": self.activo_input.isChecked(),
        }
