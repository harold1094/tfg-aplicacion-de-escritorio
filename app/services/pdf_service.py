"""Generación de PDF para facturas — 3 plantillas + bloque QR Verifactu.

Plantillas disponibles:
    • 'classic'  — Barra índigo oscura, badge de estado, tabla formal.
    • 'modern'   — Encabezado degradado morado, cards redondeadas, totales en caja.
    • 'minimal'  — Líneas finas grises, sin colores, tipografía limpia.

Todas incluyen el bloque QR de Verifactu al pie si la factura lo tiene.
Equivale a pdf-service.js del repositorio de referencia.
"""

from __future__ import annotations

import base64
from pathlib import Path

from app.models.factura import Factura
from app.services.invoice_calculator import calculate_invoice


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────

def generate_invoice_pdf(
    factura: Factura,
    output_dir: str | Path,
    template: str = "classic",
    emisor_details: dict[str, Any] | None = None,
) -> Path:
    """Genera un PDF de la factura con la plantilla elegida y lo guarda en disco."""

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as rl_canvas
    except ImportError as exc:
        raise RuntimeError("Falta instalar reportlab para generar PDFs.") from exc

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"{_safe_filename(factura.numero)}.pdf"

    totals = calculate_invoice(factura.lineas, amount_paid=factura.importe_pagado)
    pdf = rl_canvas.Canvas(str(path), pagesize=A4)
    width, height = A4

    if template == "modern":
        _render_modern(pdf, factura, totals, width, height, emisor_details)
    elif template == "minimal":
        _render_minimal(pdf, factura, totals, width, height, emisor_details)
    else:
        _render_classic(pdf, factura, totals, width, height, emisor_details)

    pdf.save()
    return path


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)


def _fmt_currency(value) -> str:
    try:
        from decimal import Decimal
        v = float(Decimal(str(value)))
        return f"{v:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"{value} €"


def _fmt_date(d) -> str:
    try:
        return d.strftime("%d/%m/%Y")
    except Exception:
        return str(d)


def _render_verifactu_block(pdf, factura: Factura, start_y: float, width, mm) -> None:
    """Añade bloque QR Verifactu al pie del PDF si la factura lo tiene."""
    qr_b64 = getattr(factura, "verifactu_qr", "") or ""
    url = getattr(factura, "verifactu_url", "") or ""
    if not qr_b64:
        return

    qr_size = 28 * mm
    margin = 20 * mm
    y = start_y - 14 * mm

    # Nueva página si no hay espacio
    if y - qr_size - 16 * mm < 10 * mm:
        pdf.showPage()
        y = 267 * mm  # A4 height − top margin

    # Línea separadora
    pdf.setStrokeColorRGB(0.78, 0.78, 0.78)
    pdf.setLineWidth(0.4)
    pdf.line(margin, y, width - margin, y)
    y -= 8 * mm

    # QR como imagen
    try:
        qr_bytes = base64.b64decode(qr_b64)
        import io
        from reportlab.lib.utils import ImageReader
        img = ImageReader(io.BytesIO(qr_bytes))
        pdf.drawImage(img, margin, y - qr_size, width=qr_size, height=qr_size)
    except Exception:
        pass

    # Texto al lado del QR
    text_x = margin + qr_size + 6 * mm
    pdf.setFont("Helvetica-Bold", 7)
    pdf.setFillColorRGB(0.31, 0.31, 0.31)
    pdf.drawString(text_x, y - 5 * mm, "Factura verificable en la AEAT — Verifactu")
    pdf.setFont("Helvetica", 7)
    pdf.setFillColorRGB(0.47, 0.47, 0.47)
    pdf.drawString(text_x, y - 11 * mm, "Escanea el código QR para verificar esta factura")
    pdf.drawString(text_x, y - 16 * mm, "en la sede electrónica de la Agencia Tributaria.")
    if url:
        pdf.setFont("Helvetica", 6)
        pdf.setFillColorRGB(0.39, 0.40, 0.95)
        short_url = url[:80] + "..." if len(url) > 80 else url
        pdf.drawString(text_x, y - 23 * mm, short_url)


# ──────────────────────────────────────────────────────────────
# Plantilla Clásica
# ──────────────────────────────────────────────────────────────

def _render_classic(pdf, factura: Factura, totals, width, height, emisor_details: dict[str, Any] | None = None) -> None:
    from reportlab.lib.units import mm

    margin = 20 * mm
    RIGHT = width - margin

    # Obtener datos de emisor dinámicos
    em_nombre = (emisor_details.get("nombre") or "Mi Empresa S.L.") if emisor_details else "Mi Empresa S.L."
    em_nif = (emisor_details.get("cif_nif") or "B12345678") if emisor_details else "B12345678"
    em_dir = (emisor_details.get("direccion_fiscal") or "Calle Principal 1") if emisor_details else "Calle Principal 1"
    em_cp = (emisor_details.get("codigo_postal") or "28001") if emisor_details else "28001"
    em_ciudad = (emisor_details.get("ciudad") or "Madrid") if emisor_details else "Madrid"
    em_correo = (emisor_details.get("correo_contacto") or "contacto@miempresa.es") if emisor_details else "contacto@miempresa.es"

    # ── Cabecera índigo oscuro ───────────────────────────────
    pdf.setFillColorRGB(0.11, 0.16, 0.35)  # Navy Blue #1b2a5a (más elegante y formal)
    pdf.rect(0, height - 42 * mm, width, 42 * mm, fill=1, stroke=0)

    # Decoración de línea fina dorada
    pdf.setFillColorRGB(0.85, 0.65, 0.13)  # Gold/Amber accent line
    pdf.rect(0, height - 44 * mm, width, 2 * mm, fill=1, stroke=0)

    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(margin, height - 26 * mm, "FACTURA")
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawRightString(RIGHT, height - 18 * mm, factura.numero)
    pdf.setFont("Helvetica", 10)
    pdf.drawRightString(RIGHT, height - 28 * mm, f"Fecha: {_fmt_date(factura.fecha)}")

    # ── Badge de estado ──────────────────────────────────────
    from app.models.factura import EstadoFactura
    is_emitted = factura.estado not in {EstadoFactura.BORRADOR, EstadoFactura.CANCELADA}
    badge_r, badge_g, badge_b = (0.09, 0.63, 0.43) if is_emitted else (0.85, 0.55, 0.0)
    pdf.setFillColorRGB(badge_r, badge_g, badge_b)
    pdf.roundRect(margin, height - 62 * mm, 32 * mm, 8 * mm, 2 * mm, fill=1, stroke=0)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawCentredString(margin + 16 * mm, height - 57.5 * mm, factura.estado.value.upper()[:10])

    # ── Emisor / Receptor ────────────────────────────────────
    y = height - 74 * mm
    pdf.setFillColorRGB(0.39, 0.39, 0.39)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(margin, y, "EMISOR")
    pdf.drawString(width / 2 + 10 * mm, y, "RECEPTOR")

    y -= 6 * mm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.setFillColorRGB(0.11, 0.16, 0.35)
    pdf.drawString(margin, y, em_nombre)
    pdf.drawString(width / 2 + 10 * mm, y, factura.cliente_nombre or "—")

    pdf.setFont("Helvetica", 9)
    pdf.setFillColorRGB(0.35, 0.35, 0.35)
    
    # Datos de emisor estructurados
    for offset, text in [
        (6 * mm, f"NIF: {em_nif}"),
        (11 * mm, em_dir),
        (16 * mm, f"{em_cp} {em_ciudad}"),
        (21 * mm, em_correo),
    ]:
        pdf.drawString(margin, y - offset, text)

    # Datos del receptor
    for offset, text in [
        (6 * mm, f"NIF: {factura.cliente_nif or '—'}"),
        (11 * mm, factura.cliente_direccion or ""),
        (16 * mm, factura.cliente_email or ""),
    ]:
        if text:
            pdf.drawString(width / 2 + 10 * mm, y - offset, text)

    # ── Separador ────────────────────────────────────────────
    y -= 27 * mm
    pdf.setStrokeColorRGB(0.85, 0.85, 0.85)
    pdf.setLineWidth(0.5)
    pdf.line(margin, y, RIGHT, y)

    # ── Tabla de líneas ──────────────────────────────────────
    y -= 5 * mm
    y = _draw_lines_table_classic(pdf, factura, y, margin, RIGHT, width, height, mm)

    # ── Totales ──────────────────────────────────────────────
    totals_x = RIGHT - 60 * mm
    y -= 10 * mm
    pdf.setFont("Helvetica", 10)
    pdf.setFillColorRGB(0.31, 0.31, 0.31)
    pdf.drawString(totals_x, y, "Base Imponible:")
    pdf.drawRightString(RIGHT, y, _fmt_currency(totals.subtotal))
    y -= 7 * mm
    pdf.drawString(totals_x, y, "IVA:")
    pdf.drawRightString(RIGHT, y, _fmt_currency(totals.iva))

    pdf.setStrokeColorRGB(0.11, 0.16, 0.35)
    pdf.setLineWidth(0.6)
    pdf.line(totals_x, y - 4 * mm, RIGHT, y - 4 * mm)
    y -= 4 * mm

    y -= 10 * mm
    pdf.setFont("Helvetica-Bold", 13)
    pdf.setFillColorRGB(0.11, 0.16, 0.35)
    pdf.drawString(totals_x, y, "TOTAL:")
    pdf.drawRightString(RIGHT, y, _fmt_currency(totals.total))

    # ── Notas ────────────────────────────────────────────────
    notes_end_y = y
    if factura.notas:
        y -= 20 * mm
        pdf.setFont("Helvetica-Bold", 9)
        pdf.setFillColorRGB(0.39, 0.39, 0.39)
        pdf.drawString(margin, y, "NOTAS")
        y -= 6 * mm
        pdf.setFont("Helvetica-Oblique", 9)
        pdf.setFillColorRGB(0.31, 0.31, 0.31)
        pdf.drawString(margin, y, factura.notas[:200])
        notes_end_y = y - 6 * mm

    _render_verifactu_block(pdf, factura, notes_end_y, width, mm)


def _draw_lines_table_classic(pdf, factura, y, margin, RIGHT, width, height, mm):
    """Dibuja la tabla de líneas para la plantilla clásica, gestiona paginación."""
    headers = ["Descripción", "Cantidad", "Precio Unit.", "IVA", "Subtotal"]
    col_x = [margin, margin + 80 * mm, margin + 100 * mm, margin + 130 * mm, margin + 150 * mm]

    # Cabecera de tabla
    pdf.setFillColorRGB(0.11, 0.16, 0.35)
    pdf.rect(margin, y - 8 * mm, RIGHT - margin, 9 * mm, fill=1, stroke=0)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 9)
    for i, h in enumerate(headers):
        pdf.drawString(col_x[i] + 2 * mm, y - 4 * mm, h)
    y -= 9 * mm

    pdf.setFont("Helvetica", 9)
    alt = False
    for linea in factura.lineas:
        if y < 45 * mm:
            pdf.showPage()
            y = height - 24 * mm
            pdf.setFont("Helvetica", 9)
        if alt:
            pdf.setFillColorRGB(0.957, 0.957, 0.980)
            pdf.rect(margin, y - 7 * mm, RIGHT - margin, 7.5 * mm, fill=1, stroke=0)
        alt = not alt
        pdf.setFillColorRGB(0.16, 0.16, 0.16)
        subtotal = linea.cantidad * linea.precio_unitario
        iva_pct = float(linea.iva * 100) if linea.iva <= 1 else float(linea.iva)
        row_vals = [
            linea.descripcion[:50],
            str(linea.cantidad),
            _fmt_currency(linea.precio_unitario),
            f"{iva_pct:.0f}%",
            _fmt_currency(subtotal),
        ]
        for i, val in enumerate(row_vals):
            pdf.drawString(col_x[i] + 2 * mm, y - 4.5 * mm, val)
        y -= 8 * mm

    return y


# ──────────────────────────────────────────────────────────────
# Plantilla Moderna
# ──────────────────────────────────────────────────────────────

def _render_modern(pdf, factura: Factura, totals, width, height, emisor_details: dict[str, Any] | None = None) -> None:
    from reportlab.lib.units import mm

    margin = 15 * mm
    RIGHT = width - margin

    # Obtener datos de emisor dinámicos
    em_nombre = (emisor_details.get("nombre") or "Mi Empresa S.L.") if emisor_details else "Mi Empresa S.L."
    em_nif = (emisor_details.get("cif_nif") or "B12345678") if emisor_details else "B12345678"
    em_dir = (emisor_details.get("direccion_fiscal") or "Calle Principal 1") if emisor_details else "Calle Principal 1"
    em_cp = (emisor_details.get("codigo_postal") or "28001") if emisor_details else "28001"
    em_ciudad = (emisor_details.get("ciudad") or "Madrid") if emisor_details else "Madrid"
    em_correo = (emisor_details.get("correo_contacto") or "contacto@miempresa.es") if emisor_details else "contacto@miempresa.es"

    # ── Encabezado degradado morado / lila moderno ──────────────────────────
    pdf.setFillColorRGB(0.35, 0.18, 0.76)  # Deep purple #582ec2
    pdf.rect(0, height - 50 * mm, width, 50 * mm, fill=1, stroke=0)
    pdf.setFillColorRGB(0.24, 0.08, 0.58)  # Even deeper purple for status bar
    pdf.rect(0, height - 12 * mm, width, 12 * mm, fill=1, stroke=0)

    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 26)
    pdf.drawString(margin, height - 30 * mm, "FACTURA")
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawRightString(RIGHT, height - 24 * mm, factura.numero)
    pdf.setFont("Helvetica", 10)
    pdf.drawRightString(RIGHT, height - 34 * mm, _fmt_date(factura.fecha))

    # ── Línea de acento lila claro ─────────────────────────────────
    pdf.setFillColorRGB(0.68, 0.54, 0.94)  # Light violet accent bar
    pdf.rect(0, height - 52 * mm, width, 2 * mm, fill=1, stroke=0)

    # ── Card Emisor ──────────────────────────────────────────
    y = height - 68 * mm
    card_w = (width / 2) - 20 * mm
    pdf.setFillColorRGB(0.97, 0.96, 1.0)  # Very light purple/lila card
    pdf.roundRect(margin - 3 * mm, y - 36 * mm, card_w, 42 * mm, 4 * mm, fill=1, stroke=0)
    
    pdf.setFont("Helvetica-Bold", 8)
    pdf.setFillColorRGB(0.35, 0.18, 0.76)
    pdf.drawString(margin, y, "DE EMISOR")
    
    pdf.setFont("Helvetica-Bold", 11)
    pdf.setFillColorRGB(0.12, 0.12, 0.22)
    pdf.drawString(margin, y - 6 * mm, em_nombre)
    
    pdf.setFont("Helvetica", 9)
    pdf.setFillColorRGB(0.35, 0.35, 0.45)
    pdf.drawString(margin, y - 13 * mm, f"NIF: {em_nif}")
    pdf.drawString(margin, y - 19 * mm, em_dir)
    pdf.drawString(margin, y - 25 * mm, f"{em_cp} {em_ciudad}")
    pdf.drawString(margin, y - 31 * mm, em_correo)

    # ── Card Receptor ────────────────────────────────────────
    rx = width / 2 + 5 * mm
    pdf.setFillColorRGB(0.95, 0.98, 0.96)  # Very light green card
    pdf.roundRect(rx - 3 * mm, y - 36 * mm, card_w, 42 * mm, 4 * mm, fill=1, stroke=0)
    
    pdf.setFont("Helvetica-Bold", 8)
    pdf.setFillColorRGB(0.06, 0.62, 0.43)  # Emerald green for receptor
    pdf.drawString(rx, y, "PARA RECEPTOR")
    
    pdf.setFont("Helvetica-Bold", 11)
    pdf.setFillColorRGB(0.12, 0.22, 0.16)
    pdf.drawString(rx, y - 6 * mm, factura.cliente_nombre or "—")
    
    pdf.setFont("Helvetica", 9)
    pdf.setFillColorRGB(0.35, 0.45, 0.40)
    pdf.drawString(rx, y - 13 * mm, f"NIF: {factura.cliente_nif or '—'}")
    if factura.cliente_direccion:
        pdf.drawString(rx, y - 19 * mm, factura.cliente_direccion)
    if factura.cliente_email:
        pdf.drawString(rx, y - 25 * mm, factura.cliente_email)

    # ── Tabla de líneas ──────────────────────────────────────
    y = height - 116 * mm
    y = _draw_lines_table_modern(pdf, factura, y, margin, RIGHT, width, height, mm)

    # ── Totales en caja redondeada morada moderna ────────────
    box_x = RIGHT - 85 * mm
    pdf.setFillColorRGB(0.35, 0.18, 0.76)
    pdf.roundRect(box_x - 5 * mm, y - 3 * mm, 90 * mm, 38 * mm, 4 * mm, fill=1, stroke=0)

    pdf.setFillColorRGB(0.85, 0.78, 0.98)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(box_x, y + 6 * mm, "Base Imponible:")
    pdf.drawRightString(RIGHT, y + 6 * mm, _fmt_currency(totals.subtotal))
    pdf.drawString(box_x, y - 2 * mm, "Impuestos (IVA):")
    pdf.drawRightString(RIGHT, y - 2 * mm, _fmt_currency(totals.iva))
    
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(box_x, y - 16 * mm, "TOTAL FACTURA")
    pdf.drawRightString(RIGHT, y - 16 * mm, _fmt_currency(totals.total))

    # ── Notas ────────────────────────────────────────────────
    modern_notes_end_y = y - 38 * mm
    if factura.notas:
        notas_y = y - 48 * mm
        pdf.setFont("Helvetica-Bold", 8)
        pdf.setFillColorRGB(0.35, 0.18, 0.76)
        pdf.drawString(margin, notas_y, "NOTAS ADICIONALES")
        pdf.setFont("Helvetica-Oblique", 9)
        pdf.setFillColorRGB(0.35, 0.35, 0.45)
        pdf.drawString(margin, notas_y - 5 * mm, factura.notas[:200])
        modern_notes_end_y = notas_y - 12 * mm

    _render_verifactu_block(pdf, factura, modern_notes_end_y, width, mm)


def _draw_lines_table_modern(pdf, factura, y, margin, RIGHT, width, height, mm):
    headers = ["Concepto", "Uds.", "Precio", "IVA", "Importe"]
    col_x = [margin, margin + 80 * mm, margin + 100 * mm, margin + 130 * mm, margin + 155 * mm]

    pdf.setFillColorRGB(0.388, 0.400, 0.945)
    pdf.rect(margin, y, RIGHT - margin, 9 * mm, fill=1, stroke=0)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 9)
    for i, h in enumerate(headers):
        pdf.drawCentredString(col_x[i] + 10 * mm, y + 3 * mm, h)
    y -= 1 * mm

    pdf.setFont("Helvetica", 9)
    for linea in factura.lineas:
        if y < 45 * mm:
            pdf.showPage()
            y = height - 24 * mm
        pdf.setFillColorRGB(0.16, 0.16, 0.16)
        subtotal = linea.cantidad * linea.precio_unitario
        iva_pct = float(linea.iva * 100) if linea.iva <= 1 else float(linea.iva)
        row_vals = [
            linea.descripcion[:50],
            str(linea.cantidad),
            _fmt_currency(linea.precio_unitario),
            f"{iva_pct:.0f}%",
            _fmt_currency(subtotal),
        ]
        for i, val in enumerate(row_vals):
            pdf.drawCentredString(col_x[i] + 10 * mm, y - 4.5 * mm, val)
        y -= 8 * mm

    return y


# ──────────────────────────────────────────────────────────────
# Plantilla Minimalista
# ──────────────────────────────────────────────────────────────

def _render_minimal(pdf, factura: Factura, totals, width, height, emisor_details: dict[str, Any] | None = None) -> None:
    from reportlab.lib.units import mm

    margin = 20 * mm
    RIGHT = width - margin

    # Obtener datos de emisor dinámicos
    em_nombre = (emisor_details.get("nombre") or "Mi Empresa S.L.") if emisor_details else "Mi Empresa S.L."
    em_nif = (emisor_details.get("cif_nif") or "B12345678") if emisor_details else "B12345678"
    em_dir = (emisor_details.get("direccion_fiscal") or "Calle Principal 1") if emisor_details else "Calle Principal 1"
    em_cp = (emisor_details.get("codigo_postal") or "28001") if emisor_details else "28001"
    em_ciudad = (emisor_details.get("ciudad") or "Madrid") if emisor_details else "Madrid"

    # ── Título ───────────────────────────────────────────────
    pdf.setFillColorRGB(0.12, 0.12, 0.12)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(margin, height - 25 * mm, "Factura")

    pdf.setFont("Helvetica", 10)
    pdf.setFillColorRGB(0.5, 0.5, 0.5)
    pdf.drawString(margin, height - 33 * mm, factura.numero)
    pdf.drawRightString(RIGHT, height - 25 * mm, f"Fecha: {_fmt_date(factura.fecha)}")

    # ── Línea fina de división minimalista ───────────────────
    pdf.setStrokeColorRGB(0.7, 0.7, 0.7)
    pdf.setLineWidth(0.8)
    pdf.line(margin, height - 40 * mm, RIGHT, height - 40 * mm)

    # ── Partes ───────────────────────────────────────────────
    y = height - 52 * mm
    pdf.setFont("Helvetica-Bold", 8)
    pdf.setFillColorRGB(0.5, 0.5, 0.5)
    pdf.drawString(margin, y, "EMISOR")
    pdf.drawString(width / 2 + 10 * mm, y, "RECEPTOR")

    y -= 6 * mm
    pdf.setFillColorRGB(0.15, 0.15, 0.15)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(margin, y, em_nombre)
    pdf.drawString(width / 2 + 10 * mm, y, factura.cliente_nombre or "—")

    y -= 6 * mm
    pdf.setFont("Helvetica", 9)
    pdf.setFillColorRGB(0.4, 0.4, 0.4)
    pdf.drawString(margin, y, f"NIF: {em_nif}")
    pdf.drawString(width / 2 + 10 * mm, y, f"NIF: {factura.cliente_nif or '—'}")
    y -= 5 * mm
    pdf.drawString(margin, y, f"{em_dir}, {em_cp} {em_ciudad}")
    cliente_addr = ", ".join(filter(None, [factura.cliente_direccion]))
    pdf.drawString(width / 2 + 10 * mm, y, cliente_addr)

    # ── Tabla de líneas ──────────────────────────────────────
    y -= 15 * mm
    y = _draw_lines_table_minimal(pdf, factura, y, margin, RIGHT, width, height, mm)

    # ── Totales ──────────────────────────────────────────────
    totals_x = RIGHT - 60 * mm
    y -= 12 * mm
    pdf.setFont("Helvetica", 9)
    pdf.setFillColorRGB(0.510, 0.510, 0.510)
    pdf.drawString(totals_x, y, "Subtotal")
    pdf.drawRightString(RIGHT, y, _fmt_currency(totals.subtotal))
    y -= 7 * mm
    pdf.drawString(totals_x, y, "IVA")
    pdf.drawRightString(RIGHT, y, _fmt_currency(totals.iva))

    pdf.setStrokeColorRGB(0.706, 0.706, 0.706)
    pdf.setLineWidth(0.5)
    pdf.line(totals_x, y - 4 * mm, RIGHT, y - 4 * mm)
    y -= 11 * mm
    pdf.setFont("Helvetica-Bold", 12)
    pdf.setFillColorRGB(0.118, 0.118, 0.118)
    pdf.drawString(totals_x, y, "Total")
    pdf.drawRightString(RIGHT, y, _fmt_currency(totals.total))

    # ── Notas ────────────────────────────────────────────────
    minimal_notes_end_y = y
    if factura.notas:
        pdf.setFont("Helvetica", 8)
        pdf.setFillColorRGB(0.627, 0.627, 0.627)
        pdf.drawString(margin, y - 25 * mm, factura.notas[:200])
        minimal_notes_end_y = y - 33 * mm

    _render_verifactu_block(pdf, factura, minimal_notes_end_y, width, mm)


def _draw_lines_table_minimal(pdf, factura, y, margin, RIGHT, width, height, mm):
    headers = ["Descripción", "Cant.", "Precio", "IVA", "Total"]
    col_x = [margin, margin + 80 * mm, margin + 100 * mm, margin + 130 * mm, margin + 150 * mm]

    # Cabecera sutil
    pdf.setFillColorRGB(0.980, 0.980, 0.980)
    pdf.rect(margin, y, RIGHT - margin, 8 * mm, fill=1, stroke=0)
    pdf.setStrokeColorRGB(0.784, 0.784, 0.784)
    pdf.setLineWidth(0.3)
    pdf.rect(margin, y, RIGHT - margin, 8 * mm, fill=0, stroke=1)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.setFillColorRGB(0.392, 0.392, 0.392)
    for i, h in enumerate(headers):
        pdf.drawString(col_x[i] + 2 * mm, y + 2 * mm, h)
    y -= 1 * mm

    pdf.setFont("Helvetica", 9)
    for linea in factura.lineas:
        if y < 45 * mm:
            pdf.showPage()
            y = height - 24 * mm
        pdf.setStrokeColorRGB(0.902, 0.902, 0.902)
        pdf.setLineWidth(0.3)
        pdf.line(margin, y - 7.5 * mm, RIGHT, y - 7.5 * mm)
        pdf.setFillColorRGB(0.196, 0.196, 0.196)
        subtotal = linea.cantidad * linea.precio_unitario
        iva_pct = float(linea.iva * 100) if linea.iva <= 1 else float(linea.iva)
        row_vals = [
            linea.descripcion[:50],
            str(linea.cantidad),
            _fmt_currency(linea.precio_unitario),
            f"{iva_pct:.0f}%",
            _fmt_currency(subtotal),
        ]
        for i, val in enumerate(row_vals):
            pdf.drawString(col_x[i] + 2 * mm, y - 4.5 * mm, val)
        y -= 8 * mm

    return y
