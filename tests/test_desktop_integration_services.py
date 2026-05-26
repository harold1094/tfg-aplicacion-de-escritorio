from datetime import date
from decimal import Decimal

import pytest

from app.controllers.factura_controller import FacturaController
from app.models.factura import EstadoFactura, LineaFactura
from app.services.ocr_stub import OcrStubService
from app.services.pdf_service import generate_invoice_pdf
from app.services.verifactu_service import VerifactuService


def test_local_invoice_lifecycle_locks_emitted_invoice():
    controller = FacturaController(supabase=None)
    invoice = controller.create_factura(
        "Cliente Demo",
        date(2026, 5, 26),
        [LineaFactura("Servicio", Decimal("1"), Decimal("100.00"))],
        cliente_email="cliente@example.com",
    )

    emitted = controller.emit_factura(invoice.id)

    assert emitted.estado == EstadoFactura.EMITIDA
    assert emitted.editable is False
    with pytest.raises(ValueError, match="borrador"):
        controller.update_factura(emitted.id, "Otro", emitted.fecha, emitted.lineas)


def test_local_invoice_payment_updates_status():
    controller = FacturaController(supabase=None)
    invoice = controller.create_factura(
        "Cliente Demo",
        date(2026, 5, 26),
        [LineaFactura("Servicio", Decimal("1"), Decimal("100.00"))],
    )
    emitted = controller.emit_factura(invoice.id)

    paid = controller.register_payment(emitted.id, Decimal("121.00"))

    assert paid.estado == EstadoFactura.PAGADA


def test_ocr_stub_prepares_manual_draft(tmp_path):
    source = tmp_path / "ticket_prueba.pdf"
    source.write_text("pendiente", encoding="utf-8")

    draft = OcrStubService().prepare_import(source)

    assert draft.status == "pendiente_ocr"
    assert draft.cliente_nombre == "Ticket Prueba"
    assert source.name in draft.descripcion


def test_pdf_generation_creates_file(tmp_path):
    reportlab = pytest.importorskip("reportlab")
    assert reportlab
    invoice = FacturaController(supabase=None).create_factura(
        "Cliente Demo",
        date(2026, 5, 26),
        [LineaFactura("Servicio", Decimal("1"), Decimal("100.00"))],
    )

    pdf = generate_invoice_pdf(invoice, tmp_path)

    assert pdf.exists()
    assert pdf.suffix == ".pdf"


def test_verifactu_requires_api_key():
    service = VerifactuService()
    if service.is_configured():
        pytest.skip("Verifactu configurado en entorno local")

    controller = FacturaController(supabase=object())
    invoice = controller.create_factura(
        "Cliente Demo",
        date(2026, 5, 26),
        [LineaFactura("Servicio", Decimal("1"), Decimal("100.00"))],
    )

    with pytest.raises(RuntimeError, match="VERIFACTI_API_KEY"):
        service.create(invoice)
