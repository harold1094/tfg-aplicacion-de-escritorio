"""Predicción ligera de gasto/facturación."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from app.models.factura import EstadoFactura, Factura
from app.services.invoice_calculator import calculate_invoice


class ForecastService:
    def forecast_next_month_amount(self, invoices: list[Factura]) -> Decimal:
        totals_by_month: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))

        for invoice in invoices:
            if invoice.estado in {EstadoFactura.BORRADOR, EstadoFactura.CANCELADA}:
                continue
            key = invoice.fecha.strftime("%Y-%m")
            totals_by_month[key] += calculate_invoice(invoice.lineas, amount_paid=invoice.importe_pagado).total

        ordered = [totals_by_month[key] for key in sorted(totals_by_month.keys())]
        if not ordered:
            return Decimal("0.00")
        if len(ordered) == 1:
            return ordered[0]
        if len(ordered) == 2:
            return (ordered[-1] + ordered[-2]) / Decimal("2")
        return (ordered[-1] * Decimal("0.5")) + (ordered[-2] * Decimal("0.3")) + (ordered[-3] * Decimal("0.2"))

    @staticmethod
    def next_month_label(reference_date: date | None = None) -> str:
        current = reference_date or date.today()
        month = 1 if current.month == 12 else current.month + 1
        year = current.year + 1 if current.month == 12 else current.year
        return f"{year}-{month:02d}"
