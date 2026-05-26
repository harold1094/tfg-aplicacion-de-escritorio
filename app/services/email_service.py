"""Envío de facturas por SMTP."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from html import escape
from pathlib import Path

from app.config import get_settings
from app.models.factura import Factura
from app.services.invoice_calculator import calculate_invoice


class EmailService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def is_configured(self) -> bool:
        return self.settings.smtp_configured

    def send_invoice(self, factura: Factura, pdf_path: str | Path | None = None) -> None:
        if not self.is_configured():
            raise RuntimeError("SMTP no está configurado en .env.")
        if not factura.cliente_email:
            raise ValueError("El cliente no tiene email.")

        totals = calculate_invoice(factura.lineas, amount_paid=factura.importe_pagado)
        sender = self.settings.smtp_from or self.settings.smtp_user

        message = EmailMessage()
        message["Subject"] = f"Factura {factura.numero}"
        message["From"] = sender
        message["To"] = factura.cliente_email
        message.set_content(
            f"Hola {factura.cliente_nombre},\n\n"
            f"Adjuntamos la factura {factura.numero} por importe de {totals.total:.2f} EUR.\n\n"
            "Gracias."
        )
        message.add_alternative(_invoice_html(factura), subtype="html")

        if pdf_path:
            path = Path(pdf_path)
            if path.exists():
                message.add_attachment(
                    path.read_bytes(),
                    maintype="application",
                    subtype="pdf",
                    filename=path.name,
                )

        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=30) as smtp:
            if self.settings.smtp_use_tls:
                smtp.starttls()
            smtp.login(self.settings.smtp_user, self.settings.smtp_password)
            smtp.send_message(message)


def _invoice_html(factura: Factura) -> str:
    totals = calculate_invoice(factura.lineas, amount_paid=factura.importe_pagado)
    rows = "".join(
        "<tr>"
        f"<td>{escape(line.descripcion)}</td>"
        f"<td>{line.cantidad}</td>"
        f"<td>{line.precio_unitario:.2f} EUR</td>"
        f"<td>{line.iva * 100:.0f}%</td>"
        f"<td>{(line.cantidad * line.precio_unitario):.2f} EUR</td>"
        "</tr>"
        for line in factura.lineas
    )
    return f"""
    <html>
      <body style="font-family:Arial,sans-serif;color:#111827">
        <h2>Factura {escape(factura.numero)}</h2>
        <p>Cliente: {escape(factura.cliente_nombre)}</p>
        <table style="width:100%;border-collapse:collapse" border="1" cellpadding="6">
          <thead>
            <tr><th>Descripcion</th><th>Cant.</th><th>Precio</th><th>IVA</th><th>Subtotal</th></tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
        <h3>Total: {totals.total:.2f} EUR</h3>
      </body>
    </html>
    """
