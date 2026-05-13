"""Vista de facturas."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.factura_controller import FacturaController
from app.services.export_csv import export_rows_to_csv
from app.services.export_excel import export_rows_to_excel
from app.services.export_xml import export_rows_to_xml


def _money(value: Decimal | str) -> str:
    return f"{Decimal(str(value)):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


class FacturasView(QWidget):
    def __init__(self, controller: FacturaController) -> None:
        super().__init__()
        self.controller = controller
        self.rows: list[dict[str, object]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Facturas")
        title.setObjectName("viewTitle")
        subtitle = QLabel("Consulta de facturas con estados profesionales y exportación a CSV, Excel y XML.")
        subtitle.setObjectName("viewSubtitle")

        toolbar = QHBoxLayout()
        new_button = QPushButton("Nueva factura")
        new_button.setEnabled(False)
        new_button.setToolTip("Disponible cuando se validen las tablas reales de Supabase")

        csv_button = QPushButton("Exportar CSV")
        excel_button = QPushButton("Exportar Excel")
        xml_button = QPushButton("Exportar XML")
        csv_button.clicked.connect(self.export_csv)
        excel_button.clicked.connect(self.export_excel)
        xml_button.clicked.connect(self.export_xml)

        toolbar.addWidget(new_button)
        toolbar.addStretch(1)
        toolbar.addWidget(csv_button)
        toolbar.addWidget(excel_button)
        toolbar.addWidget(xml_button)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["Número", "Cliente", "Fecha", "Estado", "Subtotal", "IVA", "Total", "Pendiente", "Editable"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(toolbar)
        layout.addWidget(self.table)

        self.refresh_data()

    def refresh_data(self) -> None:
        self.rows = self.controller.list_invoice_rows()
        self.table.setRowCount(len(self.rows))

        for row_index, row in enumerate(self.rows):
            values = [
                row["numero"],
                row["cliente"],
                row["fecha"],
                row["estado"],
                _money(row["subtotal"]),
                _money(row["iva"]),
                _money(row["total"]),
                _money(row["importe_pendiente"]),
                row["editable"],
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column in {4, 5, 6, 7}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row_index, column, item)

        self.table.resizeColumnsToContents()

    def export_csv(self) -> None:
        self._export("CSV", "CSV (*.csv)", export_rows_to_csv)

    def export_excel(self) -> None:
        self._export("Excel", "Excel (*.xlsx)", export_rows_to_excel)

    def export_xml(self) -> None:
        self._export("XML", "XML (*.xml)", export_rows_to_xml)

    def _export(self, label: str, file_filter: str, exporter) -> None:
        file_path, _ = QFileDialog.getSaveFileName(self, f"Exportar {label}", str(Path.home()), file_filter)
        if not file_path:
            return

        try:
            exporter(self.rows, file_path)
        except Exception as exc:
            QMessageBox.critical(self, "Error de exportación", f"No se pudo exportar el archivo:\n{exc}")
            return

        QMessageBox.information(self, "Exportación completada", f"Archivo {label} generado correctamente.")
