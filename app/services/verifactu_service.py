"""Cliente básico para Verifacti/Verifactu."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.config import get_settings
from app.models.factura import Factura
from app.services.invoice_calculator import calculate_invoice


@dataclass(frozen=True, slots=True)
class VerifactuResult:
    uuid: str = ""
    url: str = ""
    qr: str = ""


class VerifactuService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def is_configured(self) -> bool:
        return self.settings.verifacti_configured

    def create(self, factura: Factura) -> VerifactuResult:
        if not self.is_configured():
            raise RuntimeError("Verifactu no está configurado. Falta VERIFACTI_API_KEY.")

        body = _map_invoice(factura)
        request = urllib.request.Request(
            f"{self.settings.verifacti_api_base.rstrip('/')}/verifactu/create",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.verifacti_api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Error Verifactu ({exc.code}): {detail}") from exc

        return VerifactuResult(
            uuid=str(payload.get("uuid") or payload.get("id") or ""),
            url=str(payload.get("url") or payload.get("enlace") or payload.get("pdf_url") or ""),
            qr=str(payload.get("qr") or payload.get("qr_code") or payload.get("codigo_qr") or ""),
        )


def _map_invoice(factura: Factura) -> dict[str, Any]:
    totals = calculate_invoice(factura.lineas, amount_paid=factura.importe_pagado)
    iva_rate = factura.lineas[0].iva if factura.lineas else 21
    if iva_rate <= 1:
        iva_rate *= 100

    body: dict[str, Any] = {
        "serie": factura.serie or "FAC",
        "numero": str(factura.numero_factura or factura.numero),
        "fecha_expedicion": _format_date(factura.fecha),
        "tipo_factura": "F1" if factura.cliente_nif else "F2",
        "descripcion": factura.lineas[0].descripcion if factura.lineas else "Factura",
        "importe_total": f"{totals.total:.2f}",
        "lineas": [
            {
                "base_imponible": f"{totals.subtotal:.2f}",
                "tipo_impositivo": f"{iva_rate:.2f}",
                "cuota_repercutida": f"{totals.iva:.2f}",
            }
        ],
    }
    if factura.cliente_nif:
        body["nif"] = factura.cliente_nif
        body["nombre"] = factura.cliente_nombre
    return body


def _format_date(value: date) -> str:
    return value.strftime("%d-%m-%Y")
