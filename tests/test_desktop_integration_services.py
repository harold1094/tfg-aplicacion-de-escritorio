from datetime import date
from decimal import Decimal

import pytest

from app.controllers.factura_controller import FacturaController
from app.models.factura import EstadoFactura, LineaFactura
from app.services import ocr_service
from app.services.ocr_service import OcrService
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


def test_ocr_service_extracts_reviewable_draft_from_text(tmp_path):
    source = tmp_path / "ticket_prueba.txt"
    source.write_text(
        "\n".join(
            [
                "CAFETERIA MIRALMONTE",
                "C/ Mayor 1",
                "B12345678",
                "26/05/2026",
                "Cafe 2 x 1,50",
                "Tostada 3,00",
                "IVA 10% 0,60",
                "TOTAL 6,60",
            ]
        ),
        encoding="utf-8",
    )

    draft = OcrService().prepare_import(source)

    assert draft.status == "ocr_extraido"
    assert draft.cliente_nombre == "CAFETERIA MIRALMONTE"
    assert draft.cliente_nif == "B12345678"
    assert draft.fecha == date(2026, 5, 26)
    assert len(draft.lineas) == 2
    assert draft.lineas[0].descripcion == "Cafe"
    assert draft.lineas[0].cantidad == Decimal("2")
    assert draft.lineas[0].precio_unitario == Decimal("1.50")
    assert draft.lineas[0].iva == Decimal("0.10")


def test_find_tesseract_executable_prefers_env_path(monkeypatch, tmp_path):
    fake_tesseract = tmp_path / "tesseract.exe"
    fake_tesseract.write_text("", encoding="utf-8")

    monkeypatch.setenv("TESSERACT_CMD", str(fake_tesseract))
    monkeypatch.setattr(ocr_service.shutil, "which", lambda name: None)

    assert ocr_service.find_tesseract_executable() == fake_tesseract
    assert OcrService.image_ocr_ready() is True


def test_ensure_image_ocr_installed_reports_missing_winget(monkeypatch):
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.setattr(ocr_service, "find_tesseract_executable", lambda: None)
    monkeypatch.setattr(ocr_service.os, "name", "nt")
    monkeypatch.setattr(ocr_service.shutil, "which", lambda name: None)

    ok, message = OcrService.ensure_image_ocr_installed()

    assert ok is False
    assert "winget" in message


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
