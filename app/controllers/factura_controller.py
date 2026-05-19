"""Controlador de facturas."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any

from app.models.factura import AdjuntoFactura, EstadoFactura, Factura, LineaFactura
from app.services.analytics_service import AnalyticsService
from app.services.anomaly_detection_service import AnomalyDetectionService
from app.services.attachment_service import AttachmentService
from app.services.audit_service import AuditService
from app.services.classification_service import ClassificationService
from app.services.invoice_calculator import calculate_invoice, get_invoice_status
from app.services.local_store import LocalStore
from app.services.ocr_service import OCRAnalysis, OCRService
from app.supabase_client import get_supabase_client

_AUTO_SUPABASE = object()


SAMPLE_FACTURAS = [
    Factura(
        id="1",
        numero="FAC-2026-0001",
        cliente_id="1",
        cliente_nombre="Clínica Norte",
        cliente_email="administracion@clinicanorte.es",
        fecha=date(2026, 5, 2),
        fecha_vencimiento=date(2026, 5, 17),
        estado=EstadoFactura.PAGADA,
        categoria="Diseño",
        proyecto="Portal corporativo",
        lineas=[
            LineaFactura("Diseño web corporativo", Decimal("1"), Decimal("850.00")),
            LineaFactura("Licencia software", Decimal("1"), Decimal("299.00")),
        ],
        importe_pagado=Decimal("1390.29"),
        observaciones="Proyecto inicial entregado.",
    ),
    Factura(
        id="2",
        numero="FAC-2026-0002",
        cliente_id="2",
        cliente_nombre="Arquitectura Rivas",
        cliente_email="facturacion@rivas.es",
        fecha=date(2026, 5, 7),
        fecha_vencimiento=date(2026, 5, 30),
        estado=EstadoFactura.PARCIALMENTE_PAGADA,
        categoria="Soporte",
        proyecto="Mantenimiento 2026",
        lineas=[LineaFactura("Mantenimiento mensual", Decimal("6"), Decimal("120.00"))],
        importe_pagado=Decimal("300.00"),
    ),
    Factura(
        id="3",
        numero="BOR-2026-0003",
        cliente_id="3",
        cliente_nombre="Talleres Centro",
        cliente_email="compras@tallerescentro.es",
        fecha=date(2026, 5, 10),
        fecha_vencimiento=date(2026, 5, 25),
        estado=EstadoFactura.BORRADOR,
        categoria="Software",
        proyecto="Implantación",
        lineas=[LineaFactura("Licencia software", Decimal("2"), Decimal("299.00"))],
        importe_pagado=Decimal("0.00"),
    ),
]


class FacturaController:
    TABLE_NAME = "facturas"
    CLIENTES_TABLE_NAME = "clientesEmisor"

    def __init__(
        self,
        supabase: Any = _AUTO_SUPABASE,
        store: LocalStore | None = None,
        audit_service: AuditService | None = None,
        attachment_service: AttachmentService | None = None,
        classification_service: ClassificationService | None = None,
        anomaly_service: AnomalyDetectionService | None = None,
        analytics_service: AnalyticsService | None = None,
        ocr_service: OCRService | None = None,
        current_user: str = "sistema",
    ) -> None:
        self.supabase = get_supabase_client() if supabase is _AUTO_SUPABASE else supabase
        self.store = store or LocalStore()
        self.audit_service = audit_service or AuditService(self.store)
        self.attachment_service = attachment_service or AttachmentService()
        self.classification_service = classification_service or ClassificationService()
        self.anomaly_service = anomaly_service or AnomalyDetectionService()
        self.analytics_service = analytics_service or AnalyticsService()
        self.ocr_service = ocr_service or OCRService()
        self.current_user = current_user or "sistema"
        self.store.seed_bucket("facturas", [self._factura_to_row(factura) for factura in SAMPLE_FACTURAS])

    def list_facturas(self) -> list[Factura]:
        if self.supabase is not None:
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
                            "importe_pagado",
                            "fecha_vencimiento",
                            "categoria",
                            "proyecto",
                            "observaciones",
                        ]
                    )
                ).execute()
                cliente_names = self._cliente_data()
                rows = [self._map_factura(row, cliente_names) for row in response.data or []]
                if rows:
                    return rows
            except Exception:
                pass

        return [self._map_local_factura(row) for row in self.store.list_bucket("facturas")]

    def get_factura(self, factura_id: str) -> Factura | None:
        for factura in self.list_facturas():
            if factura.id == factura_id:
                return factura
        return None

    def list_invoice_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        invoices = self.list_facturas()

        for factura in invoices:
            totals = calculate_invoice(factura.lineas, amount_paid=factura.importe_pagado)
            anomalies = self.anomaly_service.detect(factura, invoices)
            display_status = (
                factura.estado
                if factura.estado in {
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
                    "fecha": factura.fecha.isoformat(),
                    "vencimiento": factura.fecha_vencimiento.isoformat() if factura.fecha_vencimiento else "",
                    "estado": display_status.value,
                    "categoria": factura.categoria,
                    "proyecto": factura.proyecto,
                    "subtotal": totals.subtotal,
                    "iva": totals.iva,
                    "total": totals.total,
                    "importe_pagado": totals.importe_pagado,
                    "importe_pendiente": totals.importe_pendiente,
                    "adjuntos": len(factura.adjuntos),
                    "anomalias": len(anomalies),
                    "editable": "Sí" if factura.editable else "No",
                }
            )

        return rows

    def dashboard_metrics(self) -> dict[str, Decimal | int]:
        snapshot = self.analytics_service.build_dashboard_snapshot(self.list_facturas())
        return {
            "total_facturado": snapshot["total_facturado"],
            "facturas_pendientes": snapshot["facturas_pendientes"],
            "facturas_vencidas": snapshot["facturas_vencidas"],
            "importe_cobrado": snapshot["importe_cobrado"],
            "importe_pendiente": snapshot["importe_pendiente"],
            "forecast_next_month": snapshot["forecast_next_month"],
        }

    def dashboard_snapshot(self) -> dict[str, object]:
        return self.analytics_service.build_dashboard_snapshot(self.list_facturas())

    def list_categories(self) -> list[str]:
        return sorted({factura.categoria for factura in self.list_facturas() if factura.categoria})

    def list_projects(self) -> list[str]:
        return sorted({factura.proyecto for factura in self.list_facturas() if factura.proyecto})

    def create_factura(self, payload: dict[str, Any], products: list[Any] | None = None) -> Factura:
        factura = self._coerce_factura(payload)
        if not factura.numero.strip():
            factura.numero = self._next_invoice_number(factura.estado)
        self._apply_classification(factura, products or [])
        row = self.store.upsert("facturas", self._factura_to_row(factura))
        result = self._map_local_factura(row)
        self.audit_service.record("factura", result.id, "create", f"Alta de factura {result.numero}", self.current_user)
        return result

    def update_factura(self, factura_id: str, payload: dict[str, Any], products: list[Any] | None = None) -> Factura:
        current = self.get_factura(factura_id)
        if current is None:
            raise ValueError("No se ha encontrado la factura seleccionada.")
        if not current.editable:
            raise ValueError("Solo se pueden editar facturas en estado BORRADOR.")

        factura = self._coerce_factura(payload, existing=current)
        factura.id = factura_id
        factura.adjuntos = current.adjuntos
        self._apply_classification(factura, products or [])
        row = self.store.upsert("facturas", self._factura_to_row(factura), row_id=factura_id)
        result = self._map_local_factura(row)
        self.audit_service.record("factura", result.id, "update", f"Actualización de factura {result.numero}", self.current_user)
        return result

    def delete_factura(self, factura_id: str) -> None:
        current = self.get_factura(factura_id)
        if current is None:
            raise ValueError("No se ha encontrado la factura seleccionada.")
        if not current.editable:
            raise ValueError("Solo se pueden eliminar borradores.")

        self.store.delete("facturas", factura_id)
        self.audit_service.record("factura", factura_id, "delete", f"Eliminación de factura {current.numero}", self.current_user)

    def register_payment(self, factura_id: str, amount: Decimal | float | str) -> Factura:
        current = self.get_factura(factura_id)
        if current is None:
            raise ValueError("No se ha encontrado la factura seleccionada.")

        new_paid_amount = current.importe_pagado + Decimal(str(amount))
        totals = calculate_invoice(current.lineas, amount_paid=new_paid_amount)
        current.importe_pagado = totals.importe_pagado
        if current.estado not in {EstadoFactura.BORRADOR, EstadoFactura.CANCELADA}:
            current.estado = get_invoice_status(totals.total, current.importe_pagado)

        row = self.store.upsert("facturas", self._factura_to_row(current), row_id=factura_id)
        result = self._map_local_factura(row)
        self.audit_service.record(
            "factura",
            result.id,
            "payment",
            f"Registro de cobro {Decimal(str(amount)):.2f} para {result.numero}",
            self.current_user,
        )
        return result

    def attach_document(self, factura_id: str, source_path: str) -> Factura:
        current = self.get_factura(factura_id)
        if current is None:
            raise ValueError("No se ha encontrado la factura seleccionada.")

        attachment = self.attachment_service.attach_file(factura_id, source_path)
        current.adjuntos.append(attachment)
        row = self.store.upsert("facturas", self._factura_to_row(current), row_id=factura_id)
        result = self._map_local_factura(row)
        self.audit_service.record(
            "factura",
            result.id,
            "attachment",
            f"Adjunto añadido a {result.numero}: {attachment.nombre_archivo}",
            self.current_user,
        )
        return result

    def analyze_document(self, source_path: str) -> OCRAnalysis:
        return self.ocr_service.analyze_document(source_path)

    def list_anomalies(self, factura_id: str) -> list[Any]:
        invoice = self.get_factura(factura_id)
        if invoice is None:
            return []
        return self.anomaly_service.detect(invoice, self.list_facturas())

    def _apply_classification(self, factura: Factura, products: list[Any]) -> None:
        if factura.categoria and factura.proyecto:
            return
        suggestion = self.classification_service.suggest(
            factura.cliente_nombre,
            [linea.descripcion for linea in factura.lineas],
            self.list_facturas(),
            products,
        )
        factura.categoria = factura.categoria or suggestion.categoria
        factura.proyecto = factura.proyecto or suggestion.proyecto

    def _coerce_factura(self, payload: dict[str, Any], existing: Factura | None = None) -> Factura:
        client_name = str(payload.get("cliente_nombre", existing.cliente_nombre if existing else "")).strip()
        if not client_name:
            raise ValueError("La factura debe tener cliente.")

        raw_lines = payload.get("lineas", existing.lineas if existing else [])
        lineas = [self._coerce_linea(item) for item in raw_lines]
        if not lineas:
            raise ValueError("La factura debe incluir al menos una línea.")

        estado = payload.get("estado", existing.estado if existing else EstadoFactura.BORRADOR)
        estado = EstadoFactura(str(getattr(estado, "value", estado)))

        fecha = payload.get("fecha", existing.fecha if existing else date.today())
        fecha_vencimiento = payload.get("fecha_vencimiento", existing.fecha_vencimiento if existing else None)
        importe_pagado = Decimal(str(payload.get("importe_pagado", existing.importe_pagado if existing else "0") or "0"))
        totals = calculate_invoice(lineas, amount_paid=importe_pagado)
        if estado not in {EstadoFactura.BORRADOR, EstadoFactura.CANCELADA}:
            estado = get_invoice_status(totals.total, totals.importe_pagado, estado)

        return Factura(
            id=existing.id if existing else "",
            numero=str(payload.get("numero", existing.numero if existing else "")).strip(),
            cliente_id=str(payload.get("cliente_id", existing.cliente_id if existing else "")).strip(),
            cliente_nombre=client_name,
            cliente_email=str(payload.get("cliente_email", existing.cliente_email if existing else "")).strip(),
            fecha=fecha if isinstance(fecha, date) else date.fromisoformat(str(fecha)),
            fecha_vencimiento=(
                fecha_vencimiento
                if isinstance(fecha_vencimiento, date) or fecha_vencimiento is None
                else date.fromisoformat(str(fecha_vencimiento))
            ),
            estado=estado,
            lineas=lineas,
            importe_pagado=totals.importe_pagado,
            categoria=str(payload.get("categoria", existing.categoria if existing else "")).strip(),
            proyecto=str(payload.get("proyecto", existing.proyecto if existing else "")).strip(),
            observaciones=str(payload.get("observaciones", existing.observaciones if existing else "")).strip(),
            adjuntos=list(existing.adjuntos) if existing else [],
        )

    @staticmethod
    def _coerce_linea(item: Any) -> LineaFactura:
        if isinstance(item, LineaFactura):
            return item
        descripcion = str(item.get("descripcion", "")).strip()
        if not descripcion:
            raise ValueError("Cada línea debe tener descripción.")
        return LineaFactura(
            descripcion=descripcion,
            cantidad=Decimal(str(item.get("cantidad", "1") or "1")),
            precio_unitario=Decimal(str(item.get("precio_unitario", "0") or "0")),
            iva=Decimal(str(item.get("iva", "0.21") or "0.21")),
        )

    def _next_invoice_number(self, estado: EstadoFactura) -> str:
        year = date.today().year
        existing = [invoice.numero for invoice in self.list_facturas()]
        counter = len(existing) + 1
        prefix = "BOR" if estado is EstadoFactura.BORRADOR else "FAC"
        return f"{prefix}-{year}-{counter:04d}"

    def _cliente_data(self) -> dict[str, dict[str, str]]:
        if self.supabase is None:
            return {}

        try:
            response = self.supabase.table(self.CLIENTES_TABLE_NAME).select("id,nombre,correo_electronico").execute()
            return {
                str(row.get("id")): {
                    "nombre": str(row.get("nombre", "")),
                    "email": str(row.get("correo_electronico", "")),
                }
                for row in response.data or []
            }
        except Exception:
            return {}

    def _map_factura(self, row: dict[str, Any], cliente_data: dict[str, dict[str, str]]) -> Factura:
        estado = _map_estado_pago(row.get("estado_pago"))
        if estado is EstadoFactura.EMITIDA and _is_draft_number(row.get("numero_factura")):
            estado = EstadoFactura.BORRADOR

        linea = _build_linea_factura(row)
        total_referencia = _to_decimal(row.get("total_factura"))
        importe_pagado = _infer_importe_pagado(row, estado, total_referencia)
        if estado is EstadoFactura.PAGADA and importe_pagado == Decimal("0.00"):
            importe_pagado = calculate_invoice([linea]).total
        id_cliente = str(row.get("id_cliente", ""))
        cliente = cliente_data.get(id_cliente, {})

        return Factura(
            id=str(row.get("id", "")),
            numero=_format_numero_factura(row),
            cliente_id=id_cliente,
            cliente_nombre=cliente.get("nombre", f"Cliente #{id_cliente}" if id_cliente else "Sin cliente"),
            cliente_email=cliente.get("email", ""),
            fecha=_parse_date(row.get("fecha_emision")),
            fecha_vencimiento=_parse_optional_date(row.get("fecha_vencimiento")),
            estado=estado,
            categoria=str(row.get("categoria", "")),
            proyecto=str(row.get("proyecto", "")),
            lineas=[linea],
            importe_pagado=importe_pagado,
            observaciones=str(row.get("observaciones", "")),
        )

    @staticmethod
    def _factura_to_row(factura: Factura) -> dict[str, Any]:
        row = asdict(factura)
        row["fecha"] = factura.fecha.isoformat()
        row["fecha_vencimiento"] = factura.fecha_vencimiento.isoformat() if factura.fecha_vencimiento else ""
        row["estado"] = factura.estado.value
        row["importe_pagado"] = str(factura.importe_pagado)
        row["lineas"] = [
            {
                "descripcion": linea.descripcion,
                "cantidad": str(linea.cantidad),
                "precio_unitario": str(linea.precio_unitario),
                "iva": str(linea.iva),
            }
            for linea in factura.lineas
        ]
        row["adjuntos"] = [asdict(adjunto) for adjunto in factura.adjuntos]
        return row

    @staticmethod
    def _map_local_factura(row: dict[str, Any]) -> Factura:
        return Factura(
            id=str(row.get("id", "")),
            numero=str(row.get("numero", "")),
            cliente_id=str(row.get("cliente_id", "")),
            cliente_nombre=str(row.get("cliente_nombre", "")),
            cliente_email=str(row.get("cliente_email", "")),
            fecha=_parse_date(row.get("fecha")),
            fecha_vencimiento=_parse_optional_date(row.get("fecha_vencimiento")),
            estado=EstadoFactura(str(row.get("estado", EstadoFactura.BORRADOR.value))),
            lineas=[
                LineaFactura(
                    descripcion=str(line.get("descripcion", "")),
                    cantidad=_to_decimal(line.get("cantidad")),
                    precio_unitario=_to_decimal(line.get("precio_unitario")),
                    iva=_to_decimal(line.get("iva", "0.21")),
                )
                for line in row.get("lineas", [])
            ],
            importe_pagado=_to_decimal(row.get("importe_pagado")),
            categoria=str(row.get("categoria", "")),
            proyecto=str(row.get("proyecto", "")),
            observaciones=str(row.get("observaciones", "")),
            adjuntos=[
                AdjuntoFactura(
                    id=str(item.get("id", "")),
                    nombre_archivo=str(item.get("nombre_archivo", "")),
                    ruta=str(item.get("ruta", "")),
                    remote_url=str(item.get("remote_url", "")),
                    tipo_mime=str(item.get("tipo_mime", "")),
                    tamano_bytes=int(item.get("tamano_bytes", 0)),
                    sha256=str(item.get("sha256", "")),
                    fecha_registro=str(item.get("fecha_registro", "")),
                )
                for item in row.get("adjuntos", [])
            ],
        )


def _to_decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0.00")
    return Decimal(str(value))


def _parse_date(value: Any) -> date:
    if value is None or value == "":
        return date.today()
    return date.fromisoformat(str(value).split("T")[0])


def _parse_optional_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
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
            iva = _normalize_tax_rate(_to_decimal(row.get("porcentaje_iva_linea") or row.get("porcentaje_iva", 21)))
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
