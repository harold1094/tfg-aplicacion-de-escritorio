"""Controlador de facturas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app.models.factura import EstadoFactura, Factura, LineaFactura
from app.services.invoice_calculator import calculate_invoice, get_invoice_status
from app.supabase_client import get_supabase_client


SAMPLE_FACTURAS = [
    Factura(
        id="1",
        numero="FAC-2026-0001",
        cliente_nombre="Clínica Norte",
        fecha=date(2026, 5, 2),
        estado=EstadoFactura.PAGADA,
        lineas=[
            LineaFactura("Diseño web corporativo", Decimal("1"), Decimal("850.00")),
            LineaFactura("Licencia software", Decimal("1"), Decimal("299.00")),
        ],
        importe_pagado=Decimal("1390.29"),
    ),
    Factura(
        id="2",
        numero="FAC-2026-0002",
        cliente_nombre="Arquitectura Rivas",
        fecha=date(2026, 5, 7),
        estado=EstadoFactura.PARCIALMENTE_PAGADA,
        lineas=[LineaFactura("Mantenimiento mensual", Decimal("6"), Decimal("120.00"))],
        importe_pagado=Decimal("300.00"),
    ),
    Factura(
        id="3",
        numero="BOR-2026-0003",
        cliente_nombre="Talleres Centro",
        fecha=date(2026, 5, 10),
        estado=EstadoFactura.BORRADOR,
        lineas=[LineaFactura("Licencia software", Decimal("2"), Decimal("299.00"))],
        importe_pagado=Decimal("0.00"),
    ),
]


class FacturaController:
    TABLE_NAME = "facturas"
    CLIENTES_TABLE_NAME = "clientesEmisor"

    def __init__(self, supabase: Any | None = None) -> None:
        self.supabase = supabase if supabase is not None else get_supabase_client()

    def list_facturas(self) -> list[Factura]:
        """Lista facturas en modo solo lectura."""

        if self.supabase is None:
            return SAMPLE_FACTURAS

        try:
            response = self.supabase.table(self.TABLE_NAME).select(
                ",".join(
                    [
                        "id",
                        "id_cliente",
                        "serie",
                        "numero_factura",
                        "fecha_emision",
                        "tipo_factura",
                        "descripcion_general",
                        "subtotal_sin_iva",
                        "porcentaje_iva",
                        "estado_pago",
                        "descripcion_producto_servicio",
                        "cantidad",
                        "unidad",
                        "precio_unitario",
                        "porcentaje_iva_linea",
                        "importe_linea",
                        "importe_iva",
                        "total_factura",
                    ]
                )
            ).execute()
            cliente_names = self._cliente_names()
            return [self._map_factura(row, cliente_names) for row in response.data or []]
        except Exception:
            return SAMPLE_FACTURAS

    def list_invoice_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        for factura in self.list_facturas():
            totals = calculate_invoice(factura.lineas, amount_paid=factura.importe_pagado)
            display_status = (
                factura.estado
                if factura.estado
                in {
                    EstadoFactura.BORRADOR,
                    EstadoFactura.CANCELADA,
                    EstadoFactura.PAGADA,
                    EstadoFactura.PARCIALMENTE_PAGADA,
                }
                else get_invoice_status(totals.total, totals.importe_pagado, factura.estado)
            )
            rows.append(
                {
                    "numero": factura.numero,
                    "cliente": factura.cliente_nombre,
                    "fecha": factura.fecha.isoformat(),
                    "estado": display_status.value,
                    "subtotal": totals.subtotal,
                    "iva": totals.iva,
                    "total": totals.total,
                    "importe_pagado": totals.importe_pagado,
                    "importe_pendiente": totals.importe_pendiente,
                    "editable": "Sí" if factura.editable else "No",
                }
            )

        return rows

    def dashboard_metrics(self) -> dict[str, Decimal | int]:
        rows = self.list_invoice_rows()
        issued_rows = [
            row
            for row in rows
            if row["estado"] not in {EstadoFactura.BORRADOR.value, EstadoFactura.CANCELADA.value}
        ]

        total_facturado = sum((Decimal(str(row["total"])) for row in issued_rows), Decimal("0.00"))
        importe_cobrado = sum((Decimal(str(row["importe_pagado"])) for row in issued_rows), Decimal("0.00"))
        importe_pendiente = sum((Decimal(str(row["importe_pendiente"])) for row in issued_rows), Decimal("0.00"))
        facturas_pendientes = sum(1 for row in issued_rows if Decimal(str(row["importe_pendiente"])) > 0)

        return {
            "total_facturado": total_facturado,
            "facturas_pendientes": facturas_pendientes,
            "importe_cobrado": importe_cobrado,
            "importe_pendiente": importe_pendiente,
        }

    def _cliente_names(self) -> dict[str, str]:
        if self.supabase is None:
            return {}

        try:
            response = self.supabase.table(self.CLIENTES_TABLE_NAME).select("id,nombre").execute()
            return {str(row.get("id")): str(row.get("nombre", "")) for row in response.data or []}
        except Exception:
            return {}

    @staticmethod
    def _map_factura(row: dict[str, Any], cliente_names: dict[str, str]) -> Factura:
        estado = _map_estado_pago(row.get("estado_pago"))
        if estado is EstadoFactura.EMITIDA and _is_draft_number(row.get("numero_factura")):
            estado = EstadoFactura.BORRADOR

        total_referencia = _to_decimal(row.get("total_factura"))
        linea = _build_linea_factura(row)
        importe_pagado = _infer_importe_pagado(row, estado, total_referencia)
        if estado is EstadoFactura.PAGADA and importe_pagado == Decimal("0.00"):
            importe_pagado = calculate_invoice([linea]).total
        id_cliente = row.get("id_cliente")

        return Factura(
            id=str(row.get("id", "")),
            numero=_format_numero_factura(row),
            cliente_nombre=cliente_names.get(str(id_cliente), f"Cliente #{id_cliente}" if id_cliente else "Sin cliente"),
            fecha=_parse_date(row.get("fecha_emision")),
            estado=estado,
            lineas=[linea],
            importe_pagado=importe_pagado,
        )


def _to_decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0.00")
    return Decimal(str(value))


def _parse_date(value: Any) -> date:
    if value is None or value == "":
        return date.today()
    return date.fromisoformat(str(value).split("T")[0])


def _format_numero_factura(row: dict[str, Any]) -> str:
    serie = str(row.get("serie") or "AUTOM")
    numero = row.get("numero_factura")
    if _is_draft_number(numero):
        return f"BOR-{row.get('id', '')}"

    try:
        return f"{serie}-{int(numero):04d}"
    except (TypeError, ValueError):
        return f"{serie}-{numero}"


def _is_draft_number(value: Any) -> bool:
    return value is None or str(value).strip() in {"", "0"}


def _map_estado_pago(value: Any) -> EstadoFactura:
    normalized = str(value or "").strip().upper().replace(" ", "_").replace("-", "_")
    mapping = {
        "": EstadoFactura.EMITIDA,
        "BORRADOR": EstadoFactura.BORRADOR,
        "DRAFT": EstadoFactura.BORRADOR,
        "EMITIDA": EstadoFactura.EMITIDA,
        "EMITIDO": EstadoFactura.EMITIDA,
        "PENDIENTE": EstadoFactura.EMITIDA,
        "PENDIENTE_DE_PAGO": EstadoFactura.EMITIDA,
        "NO_PAGADA": EstadoFactura.EMITIDA,
        "NO_PAGADO": EstadoFactura.EMITIDA,
        "PAGADA": EstadoFactura.PAGADA,
        "PAGADO": EstadoFactura.PAGADA,
        "PARCIAL": EstadoFactura.PARCIALMENTE_PAGADA,
        "PARCIALMENTE_PAGADA": EstadoFactura.PARCIALMENTE_PAGADA,
        "PARCIALMENTE_PAGADO": EstadoFactura.PARCIALMENTE_PAGADA,
        "PAGO_PARCIAL": EstadoFactura.PARCIALMENTE_PAGADA,
        "CANCELADA": EstadoFactura.CANCELADA,
        "CANCELADO": EstadoFactura.CANCELADA,
        "ANULADA": EstadoFactura.CANCELADA,
        "ANULADO": EstadoFactura.CANCELADA,
    }
    return mapping.get(normalized, EstadoFactura.EMITIDA)


def _build_linea_factura(row: dict[str, Any]) -> LineaFactura:
    cantidad = _to_decimal(row.get("cantidad")) or Decimal("1")
    precio_unitario = row.get("precio_unitario")

    if precio_unitario is None and row.get("importe_linea") is not None and cantidad:
        precio_unitario = _to_decimal(row.get("importe_linea")) / cantidad

    if precio_unitario is None:
        subtotal = _to_decimal(row.get("subtotal_sin_iva"))
        if subtotal == Decimal("0.00") and row.get("total_factura") is not None:
            iva = _normalize_tax_rate(
                _to_decimal(
                    row.get("porcentaje_iva_linea")
                    if row.get("porcentaje_iva_linea") is not None
                    else row.get("porcentaje_iva", 21)
                )
            )
            subtotal = _to_decimal(row.get("total_factura")) / (Decimal("1") + iva)
        precio_unitario = subtotal

    return LineaFactura(
        descripcion=str(
            row.get("descripcion_producto_servicio")
            or row.get("descripcion_general")
            or row.get("tipo_factura")
            or "Concepto sin descripción"
        ),
        cantidad=cantidad,
        precio_unitario=_to_decimal(precio_unitario),
        iva=_to_decimal(row.get("porcentaje_iva_linea") if row.get("porcentaje_iva_linea") is not None else row.get("porcentaje_iva", 21)),
    )


def _infer_importe_pagado(row: dict[str, Any], estado: EstadoFactura, total_factura: Decimal) -> Decimal:
    # El esquema recibido no incluye importe pagado. Si se añade en Supabase,
    # este bloque lo leerá sin cambiar el resto de la aplicación.
    for column in ("importe_pagado", "amount_paid", "pagado"):
        if column in row and row[column] is not None:
            return _to_decimal(row[column])

    if estado is EstadoFactura.PAGADA:
        return total_factura
    return Decimal("0.00")


def _normalize_tax_rate(value: Decimal) -> Decimal:
    if value > 1:
        return value / Decimal("100")
    return value
