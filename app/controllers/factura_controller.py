"""Controlador de facturas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.models.factura import EstadoFactura, Factura, LineaFactura
from app.services.invoice_calculator import calculate_invoice, get_invoice_status
from app.supabase_client import get_supabase_client


SAMPLE_FACTURAS = [
    Factura(
        id="1",
        numero="FAC-2026-0001",
        cliente_nombre="Clinica Norte",
        fecha=date(2026, 5, 2),
        estado=EstadoFactura.PAGADA,
        lineas=[
            LineaFactura("Diseno web corporativo", Decimal("1"), Decimal("850.00")),
            LineaFactura("Licencia software", Decimal("1"), Decimal("299.00")),
        ],
        importe_pagado=Decimal("1390.29"),
        cliente_email="administracion@clinicanorte.es",
        cliente_nif="B00000001",
    ),
    Factura(
        id="2",
        numero="FAC-2026-0002",
        cliente_nombre="Arquitectura Rivas",
        fecha=date(2026, 5, 7),
        estado=EstadoFactura.PARCIALMENTE_PAGADA,
        lineas=[LineaFactura("Mantenimiento mensual", Decimal("6"), Decimal("120.00"))],
        importe_pagado=Decimal("300.00"),
        cliente_email="facturacion@rivas.es",
        cliente_nif="B00000002",
    ),
    Factura(
        id="3",
        numero="BOR-2026-0003",
        cliente_nombre="Talleres Centro",
        fecha=date(2026, 5, 10),
        estado=EstadoFactura.BORRADOR,
        lineas=[LineaFactura("Licencia software", Decimal("2"), Decimal("299.00"))],
        importe_pagado=Decimal("0.00"),
        cliente_email="compras@tallerescentro.es",
        cliente_nif="B00000003",
    ),
]


class FacturaController:
    TABLE_NAME = "facturas"
    CLIENTES_TABLE_NAME = "clientesEmisor"
    SERIES_TABLE_NAME = "serieFacturacion"

    def __init__(self, supabase: Any | None = None, emisor_id: str = "") -> None:
        self.supabase = supabase if supabase is not None else get_supabase_client()
        self.emisor_id = str(emisor_id or "")
        self._local_facturas: list[Factura] | None = None

    def list_facturas(self) -> list[Factura]:
        if self._local_facturas is not None:
            return self._local_facturas

        if self.supabase is None:
            self._local_facturas = [factura for factura in SAMPLE_FACTURAS]
            return self._local_facturas
        if not self.emisor_id:
            self._local_facturas = []
            return self._local_facturas

        try:
            query = self.supabase.table(self.TABLE_NAME).select("*").eq("id_emisor", self.emisor_id)
            response = query.order("id", desc=True).execute()
            cliente_details = self._cliente_details()
            return [self._map_factura(row, cliente_details) for row in response.data or []]
        except Exception:
            self._local_facturas = []
            return self._local_facturas

    def refresh(self) -> None:
        self._local_facturas = None

    def get_factura(self, factura_id: str) -> Factura | None:
        for factura in self.list_facturas():
            if factura.id == str(factura_id):
                return factura
        return None

    def create_factura(
        self,
        cliente_nombre: str,
        fecha: date,
        lineas: list[LineaFactura],
        estado: EstadoFactura = EstadoFactura.BORRADOR,
        cliente_email: str = "",
        cliente_nif: str = "",
        cliente_direccion: str = "",
        notas: str = "",
    ) -> Factura:
        if self.supabase is not None and self.emisor_id:
            return self._create_supabase_factura(
                cliente_nombre,
                fecha,
                lineas,
                estado,
                cliente_email,
                cliente_nif,
                cliente_direccion,
                notas,
            )

        facturas = self.list_facturas()
        next_id = str(max((int(f.id) for f in facturas if f.id.isdigit()), default=0) + 1)
        prefix = "BOR" if estado is EstadoFactura.BORRADOR else "FAC"
        factura = Factura(
            id=next_id,
            numero=f"{prefix}-{date.today().year}-{int(next_id):04d}",
            cliente_nombre=cliente_nombre,
            fecha=fecha,
            estado=estado,
            lineas=lineas,
            importe_pagado=Decimal("0.00"),
            cliente_email=cliente_email,
            cliente_nif=cliente_nif,
            cliente_direccion=cliente_direccion,
            notas=notas,
        )
        facturas.insert(0, factura)
        self._local_facturas = facturas
        return factura

    def update_factura(
        self,
        factura_id: str,
        cliente_nombre: str,
        fecha: date,
        lineas: list[LineaFactura],
        cliente_email: str = "",
        cliente_nif: str = "",
        cliente_direccion: str = "",
        notas: str = "",
    ) -> Factura:
        factura = self.get_factura(factura_id)
        if factura is None:
            raise ValueError("Factura no encontrada")
        if not factura.editable:
            raise ValueError("Solo se pueden editar facturas en borrador")

        if self.supabase is not None and self.emisor_id:
            line = lineas[0]
            totals = calculate_invoice(lineas)
            payload = {
                "fecha_emision": fecha.isoformat(),
                "descripcion_general": _general_description(lineas),
                "descripcion_producto_servicio": line.descripcion,
                "cantidad": float(line.cantidad),
                "precio_unitario": float(line.precio_unitario),
                "porcentaje_iva_linea": float(_tax_percent(line.iva)),
                "porcentaje_iva": float(_tax_percent(line.iva)),
                "importe_linea": float(line.cantidad * line.precio_unitario),
                "subtotal_sin_iva": float(totals.subtotal),
                "importe_iva": float(totals.iva),
                "total_factura": float(totals.total),
                "notas": notas or None,
            }
            self.supabase.table(self.TABLE_NAME).update(payload).eq("id", factura_id).eq(
                "id_emisor", self.emisor_id
            ).execute()
            self.refresh()
            return self.get_factura(factura_id) or factura

        updated = Factura(
            id=factura.id,
            numero=factura.numero,
            cliente_nombre=cliente_nombre,
            fecha=fecha,
            estado=factura.estado,
            lineas=lineas,
            importe_pagado=factura.importe_pagado,
            cliente_id=factura.cliente_id,
            cliente_email=cliente_email or factura.cliente_email,
            cliente_nif=cliente_nif or factura.cliente_nif,
            cliente_direccion=cliente_direccion or factura.cliente_direccion,
            notas=notas,
        )
        self._replace_factura(updated)
        return updated

    def delete_factura(self, factura_id: str) -> None:
        factura = self.get_factura(factura_id)
        if factura is None:
            raise ValueError("Factura no encontrada")
        if not factura.editable:
            raise ValueError("Solo se pueden eliminar facturas en borrador")

        if self.supabase is not None and self.emisor_id:
            self.supabase.table(self.TABLE_NAME).delete().eq("id", factura_id).eq(
                "id_emisor", self.emisor_id
            ).execute()
            self.refresh()
            return

        self._local_facturas = [f for f in self.list_facturas() if f.id != str(factura_id)]

    def emit_factura(self, factura_id: str) -> Factura:
        factura = self.get_factura(factura_id)
        if factura is None:
            raise ValueError("Factura no encontrada")
        if factura.estado is EstadoFactura.CANCELADA:
            raise ValueError("No se puede emitir una factura anulada")

        if self.supabase is not None and self.emisor_id:
            serie, number = self._next_series_number(factura)
            payload = {
                "serie": serie,
                "numero_factura": number,
                "estado_pago": "pendiente",
                "estado_verifactu": "emitida",
                "fecha_creacion_registro": datetime.utcnow().isoformat(),
            }
            self.supabase.table(self.TABLE_NAME).update(payload).eq("id", factura_id).eq(
                "id_emisor", self.emisor_id
            ).execute()
            self.refresh()
            return self.get_factura(factura_id) or factura

        emitted = Factura(
            id=factura.id,
            numero=factura.numero.replace("BOR-", "FAC-", 1),
            cliente_nombre=factura.cliente_nombre,
            fecha=factura.fecha,
            estado=EstadoFactura.EMITIDA,
            lineas=factura.lineas,
            importe_pagado=factura.importe_pagado,
            cliente_email=factura.cliente_email,
            cliente_nif=factura.cliente_nif,
            cliente_direccion=factura.cliente_direccion,
            notas=factura.notas,
        )
        self._replace_factura(emitted)
        return emitted

    def register_payment(self, factura_id: str, amount: Decimal) -> Factura:
        factura = self.get_factura(factura_id)
        if factura is None:
            raise ValueError("Factura no encontrada")
        if factura.estado in {EstadoFactura.BORRADOR, EstadoFactura.CANCELADA}:
            raise ValueError("Solo se pueden registrar cobros de facturas emitidas")

        totals = calculate_invoice(factura.lineas, amount_paid=amount)
        status = get_invoice_status(totals.total, totals.importe_pagado, factura.estado)
        if self.supabase is not None and self.emisor_id:
            self.supabase.table(self.TABLE_NAME).update(
                {"importe_pagado": float(totals.importe_pagado), "estado_pago": _estado_to_supabase(status)}
            ).eq("id", factura_id).eq("id_emisor", self.emisor_id).execute()
            self.refresh()
            return self.get_factura(factura_id) or factura

        paid = Factura(
            id=factura.id,
            numero=factura.numero,
            cliente_nombre=factura.cliente_nombre,
            fecha=factura.fecha,
            estado=status,
            lineas=factura.lineas,
            importe_pagado=totals.importe_pagado,
            cliente_email=factura.cliente_email,
            cliente_nif=factura.cliente_nif,
            cliente_direccion=factura.cliente_direccion,
            notas=factura.notas,
        )
        self._replace_factura(paid)
        return paid

    def revert_to_draft(self, factura_id: str) -> Factura:
        """Compatibilidad interna: devuelve una factura emitida a borrador."""

        factura = self.get_factura(factura_id)
        if factura is None:
            raise ValueError("Factura no encontrada")
        if factura.estado is EstadoFactura.CANCELADA:
            raise ValueError("No se puede reabrir una factura anulada")

        if self.supabase is not None and self.emisor_id:
            self.supabase.table(self.TABLE_NAME).update(
                {
                    "estado_verifactu": None,
                    "fecha_creacion_registro": None,
                    "estado_pago": "borrador",
                    "importe_pagado": 0,
                }
            ).eq("id", factura_id).eq("id_emisor", self.emisor_id).execute()
            self.refresh()
            return self.get_factura(factura_id) or factura

        draft = Factura(
            id=factura.id,
            numero=factura.numero.replace("FAC-", "BOR-", 1),
            cliente_nombre=factura.cliente_nombre,
            fecha=factura.fecha,
            estado=EstadoFactura.BORRADOR,
            lineas=factura.lineas,
            importe_pagado=Decimal("0.00"),
            cliente_email=factura.cliente_email,
            cliente_nif=factura.cliente_nif,
            cliente_direccion=factura.cliente_direccion,
            notas=factura.notas,
        )
        self._replace_factura(draft)
        return draft

    def cancel_factura(self, factura_id: str) -> Factura:
        factura = self.get_factura(factura_id)
        if factura is None:
            raise ValueError("Factura no encontrada")

        if self.supabase is not None and self.emisor_id:
            self.supabase.table(self.TABLE_NAME).update({"estado_pago": "anulada"}).eq("id", factura_id).eq(
                "id_emisor", self.emisor_id
            ).execute()
            self.refresh()
            return self.get_factura(factura_id) or factura

        cancelled = Factura(
            id=factura.id,
            numero=factura.numero,
            cliente_nombre=factura.cliente_nombre,
            fecha=factura.fecha,
            estado=EstadoFactura.CANCELADA,
            lineas=factura.lineas,
            importe_pagado=factura.importe_pagado,
            cliente_email=factura.cliente_email,
            cliente_nif=factura.cliente_nif,
            cliente_direccion=factura.cliente_direccion,
            notas=factura.notas,
        )
        self._replace_factura(cancelled)
        return cancelled

    def attach_verifactu_result(self, factura_id: str, uuid: str = "", url: str = "", qr: str = "") -> None:
        if self.supabase is not None and self.emisor_id:
            self.supabase.table(self.TABLE_NAME).update(
                {"verifactu_uuid": uuid or None, "verifactu_url": url or None, "verifactu_qr": qr or None}
            ).eq("id", factura_id).eq("id_emisor", self.emisor_id).execute()
            self.refresh()
            return

        factura = self.get_factura(factura_id)
        if factura is None:
            return
        factura.verifactu_uuid = uuid
        factura.verifactu_url = url
        factura.verifactu_qr = qr

    def _replace_factura(self, updated: Factura) -> None:
        self._local_facturas = [updated if factura.id == updated.id else factura for factura in self.list_facturas()]

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
                    "id": factura.id,
                    "numero": factura.numero,
                    "cliente": factura.cliente_nombre,
                    "email": factura.cliente_email,
                    "fecha": factura.fecha.isoformat(),
                    "estado": display_status.value,
                    "subtotal": totals.subtotal,
                    "iva": totals.iva,
                    "total": totals.total,
                    "importe_pagado": totals.importe_pagado,
                    "importe_pendiente": totals.importe_pendiente,
                    "editable": "Si" if factura.editable else "No",
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

    def _create_supabase_factura(
        self,
        cliente_nombre: str,
        fecha: date,
        lineas: list[LineaFactura],
        estado: EstadoFactura,
        cliente_email: str,
        cliente_nif: str,
        cliente_direccion: str,
        notas: str,
    ) -> Factura:
        line = lineas[0]
        totals = calculate_invoice(lineas)
        cliente_id = self._find_or_create_cliente_id(
            cliente_nombre,
            cliente_email,
            cliente_nif,
            cliente_direccion,
        )
        serie = "FAC"
        numero: int | None = None
        estado_verifactu = None
        if estado is not EstadoFactura.BORRADOR:
            serie, numero = self._next_series_number(None)
            estado_verifactu = "emitida"

        payload = {
            "id_emisor": self.emisor_id,
            "id_cliente": cliente_id,
            "serie": serie,
            "numero_factura": numero,
            "fecha_emision": fecha.isoformat(),
            "tipo_factura": "factura",
            "descripcion_general": _general_description(lineas),
            "estado_pago": _estado_to_supabase(estado),
            "estado_verifactu": estado_verifactu,
            "subtotal_sin_iva": float(totals.subtotal),
            "porcentaje_iva": float(_tax_percent(line.iva)),
            "descripcion_producto_servicio": line.descripcion,
            "cantidad": float(line.cantidad),
            "unidad": "ud",
            "precio_unitario": float(line.precio_unitario),
            "porcentaje_iva_linea": float(_tax_percent(line.iva)),
            "importe_linea": float(line.cantidad * line.precio_unitario),
            "importe_iva": float(totals.iva),
            "total_factura": float(totals.total),
            "importe_pagado": 0,
            "notas": notas or None,
        }
        response = self.supabase.table(self.TABLE_NAME).insert(payload).execute()
        self.refresh()
        data = response.data[0] if response.data else None
        if data:
            return self._map_factura(data, self._cliente_details())
        return self.list_facturas()[0]

    def _cliente_details(self) -> dict[str, dict[str, str]]:
        if self.supabase is None:
            return {}

        try:
            response = self.supabase.table(self.CLIENTES_TABLE_NAME).select(
                "id,nombre,cif_nif_nie,direccion_completa,correo_electronico,telefono"
            ).execute()
            return {
                str(row.get("id")): {
                    "nombre": str(row.get("nombre") or ""),
                    "nif": str(row.get("cif_nif_nie") or ""),
                    "direccion": str(row.get("direccion_completa") or ""),
                    "email": str(row.get("correo_electronico") or ""),
                }
                for row in response.data or []
            }
        except Exception:
            return {}

    def _find_or_create_cliente_id(
        self,
        cliente_nombre: str,
        cliente_email: str = "",
        cliente_nif: str = "",
        cliente_direccion: str = "",
    ) -> str | None:
        if self.supabase is None:
            return None

        try:
            query = self.supabase.table(self.CLIENTES_TABLE_NAME).select("id,nombre,cif_nif_nie")
            if cliente_nif:
                query = query.eq("cif_nif_nie", cliente_nif)
            else:
                query = query.ilike("nombre", cliente_nombre)
            response = query.limit(1).execute()
            if response.data:
                return str(response.data[0].get("id"))
            if cliente_nif or cliente_email:
                created = (
                    self.supabase.table(self.CLIENTES_TABLE_NAME)
                    .insert(
                        {
                            "nombre": cliente_nombre,
                            "cif_nif_nie": cliente_nif or None,
                            "direccion_completa": cliente_direccion or None,
                            "correo_electronico": cliente_email or None,
                        }
                    )
                    .execute()
                )
                if created.data:
                    return str(created.data[0].get("id"))
        except Exception:
            return None
        return None

    def _next_series_number(self, factura: Factura | None) -> tuple[str, int]:
        if factura and factura.numero_factura:
            return factura.serie or "FAC", factura.numero_factura

        serie = "FAC"
        number = 1
        try:
            response = (
                self.supabase.table(self.SERIES_TABLE_NAME)
                .select("id,serie,numeroActual")
                .eq("idEmisor", self.emisor_id)
                .order("id")
                .limit(1)
                .execute()
            )
            if response.data:
                row = response.data[0]
                serie = str(row.get("serie") or "FAC")
                number = int(row.get("numeroActual") or 1)
                self.supabase.table(self.SERIES_TABLE_NAME).update({"numeroActual": number + 1}).eq(
                    "id", row.get("id")
                ).execute()
        except Exception:
            pass
        return serie, number

    @staticmethod
    def _map_factura(row: dict[str, Any], cliente_details: dict[str, dict[str, str]]) -> Factura:
        estado = _map_estado_pago(row.get("estado_pago"), row.get("estado_verifactu"), row.get("numero_factura"))
        total_referencia = _to_decimal(row.get("total_factura"))
        linea = _build_linea_factura(row)
        importe_pagado = _infer_importe_pagado(row, estado, total_referencia)
        if estado is EstadoFactura.PAGADA and importe_pagado == Decimal("0.00"):
            importe_pagado = calculate_invoice([linea]).total

        id_cliente = str(row.get("id_cliente") or "")
        cliente = cliente_details.get(id_cliente, {})
        serie = str(row.get("serie") or "FAC")
        numero_factura = _parse_int(row.get("numero_factura"))

        return Factura(
            id=str(row.get("id", "")),
            numero=_format_numero_factura(row),
            cliente_nombre=str(
                cliente.get("nombre")
                or row.get("receptor_nombre")
                or (f"Cliente #{id_cliente}" if id_cliente else "Sin cliente")
            ),
            fecha=_parse_date(row.get("fecha_emision")),
            estado=estado,
            lineas=[linea],
            importe_pagado=importe_pagado,
            cliente_id=id_cliente,
            cliente_nif=str(cliente.get("nif") or row.get("receptor_cif_nif") or ""),
            cliente_email=str(cliente.get("email") or row.get("receptor_email") or ""),
            cliente_direccion=str(cliente.get("direccion") or row.get("receptor_direccion") or ""),
            notas=str(row.get("notas") or ""),
            serie=serie,
            numero_factura=numero_factura,
            verifactu_uuid=str(row.get("verifactu_uuid") or ""),
            verifactu_url=str(row.get("verifactu_url") or ""),
            verifactu_qr=str(row.get("verifactu_qr") or ""),
        )


def _to_decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0.00")
    return Decimal(str(value))


def _parse_date(value: Any) -> date:
    if value is None or value == "":
        return date.today()
    return date.fromisoformat(str(value).split("T")[0])


def _parse_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_numero_factura(row: dict[str, Any]) -> str:
    serie = str(row.get("serie") or "FAC")
    numero = row.get("numero_factura")
    if _is_draft_number(numero):
        return f"BOR-{row.get('id', '')}"

    try:
        return f"{serie}-{int(numero):04d}"
    except (TypeError, ValueError):
        return f"{serie}-{numero}"


def _is_draft_number(value: Any) -> bool:
    return value is None or str(value).strip() in {"", "0"}


def _map_estado_pago(value: Any, estado_verifactu: Any = None, numero_factura: Any = None) -> EstadoFactura:
    normalized = str(value or "").strip().upper().replace(" ", "_").replace("-", "_")
    if normalized in {"CANCELADA", "CANCELADO", "ANULADA", "ANULADO"}:
        return EstadoFactura.CANCELADA
    if _is_draft_number(numero_factura) and not estado_verifactu:
        return EstadoFactura.BORRADOR

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
    }
    return mapping.get(normalized, EstadoFactura.EMITIDA)


def _estado_to_supabase(estado: EstadoFactura) -> str:
    mapping = {
        EstadoFactura.BORRADOR: "borrador",
        EstadoFactura.EMITIDA: "pendiente",
        EstadoFactura.PAGADA: "pagada",
        EstadoFactura.PARCIALMENTE_PAGADA: "parcial",
        EstadoFactura.CANCELADA: "anulada",
    }
    return mapping[estado]


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
            or "Concepto sin descripcion"
        ),
        cantidad=cantidad,
        precio_unitario=_to_decimal(precio_unitario),
        iva=_normalize_tax_rate(
            _to_decimal(
                row.get("porcentaje_iva_linea")
                if row.get("porcentaje_iva_linea") is not None
                else row.get("porcentaje_iva", 21)
            )
        ),
    )


def _infer_importe_pagado(row: dict[str, Any], estado: EstadoFactura, total_factura: Decimal) -> Decimal:
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


def _tax_percent(value: Decimal) -> Decimal:
    if value <= 1:
        return value * Decimal("100")
    return value


def _general_description(lines: list[LineaFactura]) -> str:
    return "; ".join(line.descripcion for line in lines)[:500]
