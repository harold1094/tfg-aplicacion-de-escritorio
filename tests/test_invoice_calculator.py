from decimal import Decimal

from app.models.factura import EstadoFactura, LineaFactura
from app.services.invoice_calculator import calculate_invoice, get_invoice_status, normalize_tax_rate


def test_calculate_invoice_totals_with_default_tax_rate():
    items = [
        {"descripcion": "Servicio", "cantidad": 2, "precio_unitario": "100.00"},
    ]

    totals = calculate_invoice(items, amount_paid="50.00")

    assert totals.subtotal == Decimal("200.00")
    assert totals.iva == Decimal("42.00")
    assert totals.total == Decimal("242.00")
    assert totals.importe_pagado == Decimal("50.00")
    assert totals.importe_pendiente == Decimal("192.00")


def test_calculate_invoice_accepts_model_lines():
    items = [LineaFactura("Producto", Decimal("3"), Decimal("10.00"), Decimal("0.10"))]

    totals = calculate_invoice(items)

    assert totals.subtotal == Decimal("30.00")
    assert totals.iva == Decimal("3.00")
    assert totals.total == Decimal("33.00")


def test_normalize_tax_rate_accepts_percentage_values():
    assert normalize_tax_rate(21) == Decimal("0.21")
    assert normalize_tax_rate("0.21") == Decimal("0.21")


def test_get_invoice_status_preserves_draft_and_cancelled():
    assert get_invoice_status("100.00", "100.00", EstadoFactura.BORRADOR) == EstadoFactura.BORRADOR
    assert get_invoice_status("100.00", "0.00", EstadoFactura.CANCELADA) == EstadoFactura.CANCELADA


def test_get_invoice_status_by_payment_amount():
    assert get_invoice_status("100.00", "0.00") == EstadoFactura.EMITIDA
    assert get_invoice_status("100.00", "40.00") == EstadoFactura.PARCIALMENTE_PAGADA
    assert get_invoice_status("100.00", "100.00") == EstadoFactura.PAGADA

