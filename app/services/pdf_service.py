"""Generación de PDF para facturas."""

from __future__ import annotations

from pathlib import Path

from app.models.factura import Factura
from app.services.invoice_calculator import calculate_invoice


def generate_invoice_pdf(factura: Factura, output_dir: str | Path) -> Path:
    """Genera un PDF sencillo y estable para adjuntar o previsualizar."""

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError("Falta instalar reportlab para generar PDFs.") from exc

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"{_safe_filename(factura.numero)}.pdf"

    totals = calculate_invoice(factura.lineas, amount_paid=factura.importe_pagado)
    pdf = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    y = height - 26 * mm

    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(22 * mm, y, "FACTURA")
    pdf.setFont("Helvetica", 12)
    pdf.drawRightString(width - 22 * mm, y, factura.numero)

    y -= 16 * mm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(22 * mm, y, "Cliente")
    pdf.setFont("Helvetica", 10)
    for value in [
        factura.cliente_nombre,
        factura.cliente_nif,
        factura.cliente_email,
        factura.cliente_direccion,
        f"Fecha: {factura.fecha.isoformat()}",
    ]:
        if value:
            y -= 6 * mm
            pdf.drawString(22 * mm, y, str(value))

    y -= 14 * mm
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(22 * mm, y, "Descripcion")
    pdf.drawRightString(128 * mm, y, "Cant.")
    pdf.drawRightString(158 * mm, y, "Precio")
    pdf.drawRightString(188 * mm, y, "Total")
    y -= 4 * mm
    pdf.line(22 * mm, y, 188 * mm, y)
    y -= 8 * mm

    pdf.setFont("Helvetica", 10)
    for line in factura.lineas:
        if y < 45 * mm:
            pdf.showPage()
            y = height - 24 * mm
            pdf.setFont("Helvetica", 10)
        subtotal = line.cantidad * line.precio_unitario
        pdf.drawString(22 * mm, y, line.descripcion[:58])
        pdf.drawRightString(128 * mm, y, str(line.cantidad))
        pdf.drawRightString(158 * mm, y, f"{line.precio_unitario:.2f} EUR")
        pdf.drawRightString(188 * mm, y, f"{subtotal:.2f} EUR")
        y -= 8 * mm

    y = max(y - 10 * mm, 45 * mm)
    pdf.line(118 * mm, y, 188 * mm, y)
    y -= 8 * mm
    pdf.drawRightString(158 * mm, y, "Base imponible")
    pdf.drawRightString(188 * mm, y, f"{totals.subtotal:.2f} EUR")
    y -= 7 * mm
    pdf.drawRightString(158 * mm, y, "IVA")
    pdf.drawRightString(188 * mm, y, f"{totals.iva:.2f} EUR")
    y -= 9 * mm
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawRightString(158 * mm, y, "TOTAL")
    pdf.drawRightString(188 * mm, y, f"{totals.total:.2f} EUR")

    pdf.save()
    return path


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)
