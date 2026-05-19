from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.factura import AdjuntoFactura, EstadoFactura, Factura, LineaFactura
from app.models.producto import Producto
from app.services.anomaly_detection_service import AnomalyDetectionService
from app.services.classification_service import ClassificationService
from app.services.forecast_service import ForecastService


def build_invoice(
    invoice_id: str,
    numero: str,
    cliente: str,
    total: str,
    *,
    categoria: str = "",
    proyecto: str = "",
    estado: EstadoFactura = EstadoFactura.EMITIDA,
    fecha: date = date(2026, 5, 1),
    vencimiento: date | None = None,
    attachment_hash: str = "",
) -> Factura:
    attachment = []
    if attachment_hash:
        attachment.append(
            AdjuntoFactura(
                id="a1",
                nombre_archivo="doc.pdf",
                ruta="/tmp/doc.pdf",
                tipo_mime="application/pdf",
                tamano_bytes=10,
                sha256=attachment_hash,
                fecha_registro="2026-05-01T10:00:00",
            )
        )
    return Factura(
        id=invoice_id,
        numero=numero,
        cliente_id=invoice_id,
        cliente_nombre=cliente,
        cliente_email=f"{cliente.lower()}@example.com",
        fecha=fecha,
        fecha_vencimiento=vencimiento,
        estado=estado,
        categoria=categoria,
        proyecto=proyecto,
        lineas=[LineaFactura("Servicio", Decimal("1"), Decimal(total))],
        importe_pagado=Decimal("0.00"),
        adjuntos=attachment,
    )


def test_classification_service_prefers_client_history():
    history = [
        build_invoice("1", "FAC-1", "Cliente Uno", "100.00", categoria="Diseño", proyecto="Web A"),
        build_invoice("2", "FAC-2", "Cliente Uno", "150.00", categoria="Diseño", proyecto="Web A"),
    ]
    products = [Producto("p1", "Mantenimiento", "Servicio", Decimal("50.00"), "SERVICIO", "Soporte")]

    suggestion = ClassificationService().suggest("Cliente Uno", ["Consultoría"], history, products)

    assert suggestion.categoria == "Diseño"
    assert suggestion.proyecto == "Web A"


def test_anomaly_detection_flags_duplicate_number_and_document():
    base = build_invoice("1", "FAC-100", "Cliente Uno", "100.00", attachment_hash="abc")
    duplicate = build_invoice("2", "FAC-100", "Cliente Dos", "120.00", attachment_hash="abc")

    anomalies = AnomalyDetectionService().detect(base, [base, duplicate])

    codes = {item.code for item in anomalies}
    assert "duplicate_number" in codes
    assert "duplicate_document" in codes


def test_forecast_service_uses_recent_weighted_average():
    invoices = [
        build_invoice("1", "FAC-1", "A", "100.00", fecha=date(2026, 1, 5)),
        build_invoice("2", "FAC-2", "A", "200.00", fecha=date(2026, 2, 5)),
        build_invoice("3", "FAC-3", "A", "300.00", fecha=date(2026, 3, 5)),
    ]

    forecast = ForecastService().forecast_next_month_amount(invoices)

    assert forecast == Decimal("278.300")
