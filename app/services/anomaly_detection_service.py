"""Detección de anomalías sobre facturas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.models.factura import EstadoFactura, Factura
from app.services.invoice_calculator import calculate_invoice


@dataclass(frozen=True, slots=True)
class InvoiceAnomaly:
    code: str
    severity: str
    message: str


class AnomalyDetectionService:
    def detect(self, invoice: Factura, invoices: list[Factura]) -> list[InvoiceAnomaly]:
        anomalies: list[InvoiceAnomaly] = []
        totals = calculate_invoice(invoice.lineas, amount_paid=invoice.importe_pagado)

        if not invoice.cliente_nombre.strip():
            anomalies.append(InvoiceAnomaly("missing_client", "high", "La factura no tiene cliente asignado."))
        if not invoice.lineas:
            anomalies.append(InvoiceAnomaly("missing_lines", "high", "La factura no tiene líneas de detalle."))
        if invoice.fecha_vencimiento and invoice.fecha_vencimiento < invoice.fecha and invoice.estado != EstadoFactura.CANCELADA:
            anomalies.append(
                InvoiceAnomaly("invalid_due_date", "medium", "La fecha de vencimiento es anterior a la fecha de emisión.")
            )
        if invoice.fecha_vencimiento and invoice.fecha_vencimiento < date.today() and totals.importe_pendiente > 0:
            anomalies.append(InvoiceAnomaly("overdue", "medium", "La factura está vencida y mantiene saldo pendiente."))

        duplicates = [
            current
            for current in invoices
            if current.id != invoice.id and current.numero.strip() and current.numero == invoice.numero
        ]
        if duplicates:
            anomalies.append(
                InvoiceAnomaly("duplicate_number", "high", "Existe otra factura con el mismo número identificativo.")
            )

        attachment_hashes = {attachment.sha256 for attachment in invoice.adjuntos}
        if attachment_hashes:
            for current in invoices:
                if current.id == invoice.id:
                    continue
                if attachment_hashes.intersection({attachment.sha256 for attachment in current.adjuntos}):
                    anomalies.append(
                        InvoiceAnomaly(
                            "duplicate_document",
                            "high",
                            "Se ha detectado un documento adjunto idéntico en otra factura.",
                        )
                    )
                    break

        same_client = [current for current in invoices if current.id != invoice.id and current.cliente_nombre == invoice.cliente_nombre]
        if len(same_client) >= 2:
            historical_totals = [calculate_invoice(current.lineas, amount_paid=current.importe_pagado).total for current in same_client]
            avg_total = sum(historical_totals, Decimal("0.00")) / Decimal(len(historical_totals))
            if avg_total > 0 and (totals.total > avg_total * Decimal("1.8") or totals.total < avg_total * Decimal("0.4")):
                anomalies.append(
                    InvoiceAnomaly(
                        "unusual_amount",
                        "medium",
                        "El importe total se desvía de forma notable del histórico del cliente.",
                    )
                )

        return anomalies
