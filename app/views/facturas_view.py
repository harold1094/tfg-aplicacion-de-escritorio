"""Vista de facturas."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config import get_settings
from app.controllers.cliente_controller import ClienteController
from app.controllers.factura_controller import FacturaController
from app.controllers.producto_controller import ProductoController
from app.models.security import UserPermissions
from app.services.backup_service import BackupService
from app.services.email_service import EmailService
from app.services.export_csv import export_rows_to_csv
from app.services.export_excel import export_rows_to_excel
from app.services.export_pdf import export_rows_to_pdf
from app.services.export_xml import export_rows_to_xml
from app.services.invoice_calculator import calculate_invoice
from app.views.async_utils import BackgroundRunner
from app.views.factura_dialog import FacturaDialog
from app.views.payment_dialog import PaymentDialog


def _money(value: Decimal | str) -> str:
    return f"{Decimal(str(value)):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


class FacturasView(QWidget):
    def __init__(
        self,
        controller: FacturaController,
        cliente_controller: ClienteController,
        producto_controller: ProductoController,
        permissions: UserPermissions,
        email_service: EmailService | None = None,
    ) -> None:
        super().__init__()
        self.controller = controller
        self.cliente_controller = cliente_controller
        self.producto_controller = producto_controller
        self.permissions = permissions
        self.email_service = email_service or EmailService()
        self.backup_service = BackupService()
        self.background_runner = BackgroundRunner()
        self.settings = get_settings()
        self.rows: list[dict[str, object]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Facturas")
        title.setObjectName("viewTitle")
        subtitle = QLabel("Gestión completa de facturas, cobros, adjuntos, anomalías y exportación profesional.")
        subtitle.setObjectName("viewSubtitle")

        toolbar = QHBoxLayout()
        self.new_button = QPushButton("Nueva")
        self.edit_button = QPushButton("Editar")
        self.delete_button = QPushButton("Eliminar")
        self.payment_button = QPushButton("Registrar cobro")
        self.attach_button = QPushButton("Adjuntar")
        self.analyze_button = QPushButton("Analizar adjunto")
        self.send_button = QPushButton("Enviar email")
        self.backup_button = QPushButton("Crear backup")

        self.new_button.clicked.connect(self.create_invoice)
        self.edit_button.clicked.connect(self.edit_selected_invoice)
        self.delete_button.clicked.connect(self.delete_selected_invoice)
        self.payment_button.clicked.connect(self.register_payment)
        self.attach_button.clicked.connect(self.attach_document)
        self.analyze_button.clicked.connect(self.analyze_document)
        self.send_button.clicked.connect(self.send_invoice_email)
        self.backup_button.clicked.connect(self.create_backup)

        toolbar.addWidget(self.new_button)
        toolbar.addWidget(self.edit_button)
        toolbar.addWidget(self.delete_button)
        toolbar.addWidget(self.payment_button)
        toolbar.addWidget(self.attach_button)
        toolbar.addWidget(self.analyze_button)
        toolbar.addWidget(self.send_button)
        toolbar.addWidget(self.backup_button)
        toolbar.addStretch(1)

        export_toolbar = QHBoxLayout()
        csv_button = QPushButton("Exportar CSV")
        excel_button = QPushButton("Exportar Excel")
        xml_button = QPushButton("Exportar XML")
        pdf_button = QPushButton("Exportar PDF")
        csv_button.clicked.connect(self.export_csv)
        excel_button.clicked.connect(self.export_excel)
        xml_button.clicked.connect(self.export_xml)
        pdf_button.clicked.connect(self.export_pdf)
        export_toolbar.addStretch(1)
        export_toolbar.addWidget(csv_button)
        export_toolbar.addWidget(excel_button)
        export_toolbar.addWidget(xml_button)
        export_toolbar.addWidget(pdf_button)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            ["Id", "Número", "Cliente", "Fecha", "Vencimiento", "Estado", "Categoría", "Total", "Pendiente", "Alertas"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.itemSelectionChanged.connect(self.refresh_details)
        self.table.itemDoubleClicked.connect(lambda _: self.edit_selected_invoice())
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.ResizeToContents)

        self.detail_tabs = QTabWidget()
        self.lines_table = QTableWidget(0, 4)
        self.lines_table.setHorizontalHeaderLabels(["Descripción", "Cantidad", "Precio", "IVA"])
        self.lines_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.lines_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.lines_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.lines_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        self.attachments_table = QTableWidget(0, 5)
        self.attachments_table.setHorizontalHeaderLabels(["Archivo", "Origen", "Tipo", "Tamaño", "Fecha"])
        self.attachments_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.attachments_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.attachments_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.attachments_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.attachments_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self.anomalies_list = QListWidget()
        self.summary_label = QLabel("Selecciona una factura para ver el detalle.")
        self.summary_label.setWordWrap(True)
        self.summary_label.setObjectName("viewSubtitle")

        lines_tab = QWidget()
        lines_layout = QVBoxLayout(lines_tab)
        lines_layout.addWidget(self.lines_table)

        attachments_tab = QWidget()
        attachments_layout = QVBoxLayout(attachments_tab)
        attachments_layout.addWidget(self.attachments_table)

        anomalies_tab = QWidget()
        anomalies_layout = QVBoxLayout(anomalies_tab)
        anomalies_layout.addWidget(self.anomalies_list)

        self.detail_tabs.addTab(lines_tab, "Líneas")
        self.detail_tabs.addTab(attachments_tab, "Adjuntos")
        self.detail_tabs.addTab(anomalies_tab, "Alertas")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(toolbar)
        layout.addLayout(export_toolbar)
        layout.addWidget(self.table)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.detail_tabs)

        self.apply_permissions()
        self.refresh_data()

    def apply_permissions(self) -> None:
        self.delete_button.setEnabled(self.permissions.can_delete_invoices)
        self.send_button.setEnabled(self.permissions.can_send_email)
        self.backup_button.setEnabled(self.permissions.can_manage_master_data)
        if not self.permissions.can_delete_invoices:
            self.delete_button.setToolTip("Disponible solo para el rol administrador.")
        if not self.permissions.can_manage_master_data:
            self.backup_button.setToolTip("Disponible solo para el rol administrador.")

    def refresh_data(self) -> None:
        self.rows = self.controller.list_invoice_rows()
        self.table.setRowCount(len(self.rows))

        for row_index, row in enumerate(self.rows):
            values = [
                row["id"],
                row["numero"],
                row["cliente"],
                row["fecha"],
                row["vencimiento"],
                row["estado"],
                row["categoria"],
                _money(row["total"]),
                _money(row["importe_pendiente"]),
                str(row["anomalias"]),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column in {7, 8, 9}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row_index, column, item)
        self.table.setColumnHidden(0, True)
        if self.rows:
            self.table.selectRow(0)
        self.refresh_details()

    def current_invoice_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.rows):
            return None
        return str(self.rows[row]["id"])

    def current_invoice(self):
        invoice_id = self.current_invoice_id()
        if invoice_id is None:
            return None
        return self.controller.get_factura(invoice_id)

    def refresh_details(self) -> None:
        invoice = self.current_invoice()
        self.lines_table.setRowCount(0)
        self.attachments_table.setRowCount(0)
        self.anomalies_list.clear()

        if invoice is None:
            self.summary_label.setText("Selecciona una factura para ver el detalle.")
            return

        totals = calculate_invoice(invoice.lineas, amount_paid=invoice.importe_pagado)
        self.summary_label.setText(
            f"{invoice.numero} | Cliente: {invoice.cliente_nombre} | Proyecto: {invoice.proyecto or '-'} | "
            f"Total: {_money(totals.total)} | Cobrado: {_money(totals.importe_pagado)} | Pendiente: {_money(totals.importe_pendiente)}"
        )

        for linea in invoice.lineas:
            row = self.lines_table.rowCount()
            self.lines_table.insertRow(row)
            values = [linea.descripcion, str(linea.cantidad), _money(linea.precio_unitario), str(linea.iva)]
            for column, value in enumerate(values):
                self.lines_table.setItem(row, column, QTableWidgetItem(value))

        for attachment in invoice.adjuntos:
            row = self.attachments_table.rowCount()
            self.attachments_table.insertRow(row)
            origin = "Supabase" if attachment.remote_url else "Local"
            values = [attachment.nombre_archivo, origin, attachment.tipo_mime, str(attachment.tamano_bytes), attachment.fecha_registro]
            for column, value in enumerate(values):
                self.attachments_table.setItem(row, column, QTableWidgetItem(value))

        for anomaly in self.controller.list_anomalies(invoice.id):
            self.anomalies_list.addItem(f"[{anomaly.severity}] {anomaly.message}")

    def create_invoice(self) -> None:
        dialog = FacturaDialog(
            clientes=self.cliente_controller.list_clientes(),
            categories=self.controller.list_categories() + self.producto_controller.list_categories(),
            projects=self.controller.list_projects(),
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        try:
            self.controller.create_factura(dialog.get_payload(), products=self.producto_controller.list_productos())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        self.refresh_data()

    def edit_selected_invoice(self) -> None:
        invoice = self.current_invoice()
        if invoice is None:
            return

        dialog = FacturaDialog(
            clientes=self.cliente_controller.list_clientes(),
            categories=self.controller.list_categories() + self.producto_controller.list_categories(),
            projects=self.controller.list_projects(),
            factura=invoice,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        try:
            self.controller.update_factura(invoice.id, dialog.get_payload(), products=self.producto_controller.list_productos())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        self.refresh_data()

    def delete_selected_invoice(self) -> None:
        invoice = self.current_invoice()
        if invoice is None:
            return
        if QMessageBox.question(self, "Confirmar", f"¿Eliminar la factura {invoice.numero}?") != QMessageBox.StandardButton.Yes:
            return

        try:
            self.controller.delete_factura(invoice.id)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        self.refresh_data()

    def register_payment(self) -> None:
        invoice = self.current_invoice()
        if invoice is None:
            return
        dialog = PaymentDialog()
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        try:
            self.controller.register_payment(invoice.id, dialog.amount())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        self.refresh_data()

    def attach_document(self) -> None:
        invoice = self.current_invoice()
        if invoice is None:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Adjuntar documento",
            str(Path.home()),
            "Documentos (*.pdf *.png *.jpg *.jpeg *.txt *.xml *.csv)",
        )
        if not file_path:
            return

        self._set_busy(True, "Adjuntando documento...")
        self.background_runner.submit(
            self.controller.attach_document,
            invoice.id,
            file_path,
            on_success=lambda _result: self._finish_background("Adjunto registrado correctamente.", refresh=True),
            on_error=self._background_error,
        )

    def analyze_document(self) -> None:
        invoice = self.current_invoice()
        if invoice is None or not invoice.adjuntos:
            QMessageBox.information(self, "Análisis", "La factura no tiene adjuntos para analizar.")
            return

        self._set_busy(True, "Analizando documento...")
        self.background_runner.submit(
            self.controller.analyze_document,
            invoice.adjuntos[-1].ruta,
            on_success=self._show_analysis_result,
            on_error=self._background_error,
        )

    def send_invoice_email(self) -> None:
        invoice = self.current_invoice()
        if invoice is None:
            return

        export_path = self.settings.exports_dir / f"{invoice.numero}.pdf"
        row = next((item for item in self.rows if item["id"] == invoice.id), None)
        if row is None:
            return
        export_rows_to_pdf([row], export_path, title=f"Factura {invoice.numero}")

        self._set_busy(True, "Enviando email...")
        self.background_runner.submit(
            self.email_service.send_invoice_email,
            recipient=invoice.cliente_email,
            subject=f"Factura {invoice.numero}",
            body=f"Adjuntamos la factura {invoice.numero} generada desde la aplicación de escritorio.",
            attachment_path=export_path,
            on_success=self._handle_email_result,
            on_error=self._background_error,
        )

    def create_backup(self) -> None:
        self._set_busy(True, "Generando copia de seguridad...")
        self.background_runner.submit(
            self.backup_service.create_backup,
            on_success=lambda path: self._finish_background(f"Backup creado en {path}", refresh=False),
            on_error=self._background_error,
        )

    def export_csv(self) -> None:
        self._export("CSV", "CSV (*.csv)", export_rows_to_csv)

    def export_excel(self) -> None:
        self._export("Excel", "Excel (*.xlsx)", export_rows_to_excel)

    def export_xml(self) -> None:
        self._export("XML", "XML (*.xml)", export_rows_to_xml)

    def export_pdf(self) -> None:
        self._export("PDF", "PDF (*.pdf)", export_rows_to_pdf)

    def _export(self, label: str, file_filter: str, exporter) -> None:
        file_path, _ = QFileDialog.getSaveFileName(self, f"Exportar {label}", str(Path.home()), file_filter)
        if not file_path:
            return

        self._set_busy(True, f"Exportando {label}...")
        self.background_runner.submit(
            exporter,
            self.rows,
            file_path,
            on_success=lambda _result: self._finish_background(f"Archivo {label} generado correctamente.", refresh=False),
            on_error=self._background_error,
        )

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self.summary_label.setText(message or self.summary_label.text())
        buttons = [
            self.new_button,
            self.edit_button,
            self.delete_button,
            self.payment_button,
            self.attach_button,
            self.analyze_button,
            self.send_button,
            self.backup_button,
        ]
        for button in buttons:
            button.setEnabled(not busy)
        if not busy:
            self.apply_permissions()
            self.new_button.setEnabled(True)
            self.edit_button.setEnabled(True)
            self.payment_button.setEnabled(True)
            self.attach_button.setEnabled(True)
            self.analyze_button.setEnabled(True)

    def _finish_background(self, message: str, refresh: bool) -> None:
        self._set_busy(False)
        if refresh:
            self.refresh_data()
        QMessageBox.information(self, "Operación completada", message)

    def _background_error(self, error: str) -> None:
        self._set_busy(False)
        QMessageBox.critical(self, "Error", error)

    def _show_analysis_result(self, analysis) -> None:
        self._set_busy(False)
        warnings = "\n".join(f"- {warning}" for warning in analysis.warnings) if analysis.warnings else "Sin advertencias."
        QMessageBox.information(
            self,
            "Resultado del análisis",
            f"Proveedor: {analysis.provider_guess}\n"
            f"Número: {analysis.invoice_number or '-'}\n"
            f"Fecha: {analysis.invoice_date or '-'}\n"
            f"Importe detectado: {analysis.total_amount if analysis.total_amount is not None else '-'}\n\n"
            f"Notas:\n{warnings}",
        )

    def _handle_email_result(self, result) -> None:
        self._set_busy(False)
        if result.success:
            QMessageBox.information(self, "Email", result.message)
        else:
            QMessageBox.critical(self, "Email", result.message)
