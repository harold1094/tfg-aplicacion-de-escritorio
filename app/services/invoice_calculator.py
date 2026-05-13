"""Reglas de cálculo de facturas."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

from app.models.factura import EstadoFactura


MONEY_QUANTIZER = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class InvoiceTotals:
    subtotal: Decimal
    iva: Decimal
    total: Decimal
    importe_pagado: Decimal
    importe_pendiente: Decimal


def to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def round_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTIZER, rounding=ROUND_HALF_UP)


def normalize_tax_rate(value: Any) -> Decimal:
    rate = to_decimal(value)
    if rate > 1:
        return rate / Decimal("100")
    return rate


def _read_value(item: Any, *names: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        for name in names:
            if name in item:
                return item[name]
        return default

    for name in names:
        if hasattr(item, name):
            return getattr(item, name)
    return default


def calculate_invoice(
    items: Iterable[Any],
    default_tax_rate: Decimal | float | str = Decimal("0.21"),
    amount_paid: Decimal | float | str = Decimal("0.00"),
) -> InvoiceTotals:
    """Calcula importes principales a partir de líneas de factura.

    Cada línea puede ser un diccionario o un objeto con estos campos:
    cantidad/quantity, precio_unitario/unit_price/precio/price e iva/tax_rate.
    """

    subtotal = Decimal("0.00")
    tax_amount = Decimal("0.00")
    fallback_tax_rate = normalize_tax_rate(default_tax_rate)

    for item in items:
        quantity = to_decimal(_read_value(item, "cantidad", "quantity", default=1))
        unit_price = to_decimal(
            _read_value(item, "precio_unitario", "unit_price", "precio", "price", default=0)
        )
        tax_rate = normalize_tax_rate(_read_value(item, "iva", "tax_rate", default=fallback_tax_rate))

        line_subtotal = quantity * unit_price
        subtotal += line_subtotal
        tax_amount += line_subtotal * tax_rate

    subtotal = round_money(subtotal)
    tax_amount = round_money(tax_amount)
    total = round_money(subtotal + tax_amount)
    paid = round_money(to_decimal(amount_paid))
    pending = round_money(max(total - paid, Decimal("0.00")))

    return InvoiceTotals(
        subtotal=subtotal,
        iva=tax_amount,
        total=total,
        importe_pagado=paid,
        importe_pendiente=pending,
    )


def get_invoice_status(
    total: Decimal | float | str,
    amount_paid: Decimal | float | str,
    current_status: EstadoFactura | str | None = None,
) -> EstadoFactura:
    """Determina el estado de pago sin sobrescribir borradores o cancelaciones."""

    if current_status is not None:
        status = EstadoFactura(current_status)
        if status in {EstadoFactura.BORRADOR, EstadoFactura.CANCELADA}:
            return status

    total_amount = round_money(to_decimal(total))
    paid_amount = round_money(to_decimal(amount_paid))

    if paid_amount <= 0:
        return EstadoFactura.EMITIDA
    if paid_amount >= total_amount:
        return EstadoFactura.PAGADA
    return EstadoFactura.PARCIALMENTE_PAGADA

