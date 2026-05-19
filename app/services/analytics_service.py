"""Analítica y KPIs del dashboard."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from app.models.factura import EstadoFactura, Factura
from app.services.forecast_service import ForecastService
from app.services.invoice_calculator import calculate_invoice


class AnalyticsService:
    def __init__(self, forecast_service: ForecastService | None = None) -> None:
        self.forecast_service = forecast_service or ForecastService()

    def build_dashboard_snapshot(self, invoices: list[Factura]) -> dict[str, object]:
        issued_invoices = [
            invoice for invoice in invoices if invoice.estado not in {EstadoFactura.BORRADOR, EstadoFactura.CANCELADA}
        ]

        total_facturado = Decimal("0.00")
        importe_cobrado = Decimal("0.00")
        importe_pendiente = Decimal("0.00")
        facturas_pendientes = 0
        facturas_vencidas = 0
        totals_by_month: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        totals_by_client: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))

        for invoice in issued_invoices:
            totals = calculate_invoice(invoice.lineas, amount_paid=invoice.importe_pagado)
            total_facturado += totals.total
            importe_cobrado += totals.importe_pagado
            importe_pendiente += totals.importe_pendiente
            totals_by_month[invoice.fecha.strftime("%Y-%m")] += totals.total
            totals_by_client[invoice.cliente_nombre or "Sin cliente"] += totals.total
            if totals.importe_pendiente > 0:
                facturas_pendientes += 1
            if invoice.fecha_vencimiento and invoice.fecha_vencimiento < date.today() and totals.importe_pendiente > 0:
                facturas_vencidas += 1

        monthly_series = [
            {"label": label, "value": value}
            for label, value in sorted(totals_by_month.items())[-6:]
        ]
        top_cliente = ""
        if totals_by_client:
            top_cliente = max(totals_by_client.items(), key=lambda item: item[1])[0]

        return {
            "total_facturado": total_facturado,
            "facturas_pendientes": facturas_pendientes,
            "facturas_vencidas": facturas_vencidas,
            "importe_cobrado": importe_cobrado,
            "importe_pendiente": importe_pendiente,
            "top_cliente": top_cliente,
            "forecast_next_month": self.forecast_service.forecast_next_month_amount(issued_invoices),
            "forecast_label": self.forecast_service.next_month_label(),
            "monthly_series": monthly_series,
        }
