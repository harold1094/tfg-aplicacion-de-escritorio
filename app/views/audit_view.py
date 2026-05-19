"""Vista de auditoría."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.audit_controller import AuditController


class AuditView(QWidget):
    def __init__(self, controller: AuditController) -> None:
        super().__init__()
        self.controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Actividad")
        title.setObjectName("viewTitle")
        subtitle = QLabel("Registro de cambios relevantes realizados desde la aplicación.")
        subtitle.setObjectName("viewSubtitle")

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar en auditoría")
        self.search_input.textChanged.connect(self.refresh_data)
        toolbar.addWidget(self.search_input, 1)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Fecha", "Acción", "Entidad", "Descripción", "Usuario"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(toolbar)
        layout.addWidget(self.table)

        self.refresh_data()

    def refresh_data(self) -> None:
        entries = self.controller.list_entries(self.search_input.text() if hasattr(self, "search_input") else "")
        self.table.setRowCount(len(entries))

        for row_index, entry in enumerate(entries):
            values = [entry.created_at, entry.action, entry.entity_type, entry.description, entry.user_email]
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, QTableWidgetItem(str(value)))
