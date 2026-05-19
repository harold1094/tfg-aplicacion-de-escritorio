"""Controlador de productos y servicios."""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from typing import Any

from app.models.producto import Producto
from app.services.audit_service import AuditService
from app.services.local_store import LocalStore
from app.supabase_client import get_supabase_client

_AUTO_SUPABASE = object()


SAMPLE_PRODUCTOS = [
    Producto("1", "Diseño web corporativo", "Servicio de diseño y maquetación inicial", Decimal("850.00"), "SERVICIO", "Diseño"),
    Producto("2", "Mantenimiento mensual", "Soporte técnico y actualizaciones", Decimal("120.00"), "SERVICIO", "Soporte"),
    Producto("3", "Licencia software", "Licencia anual de herramienta de gestión", Decimal("299.00"), "PRODUCTO", "Software"),
]


class ProductoController:
    TABLE_NAME = "productos_servicios"
    FACTURAS_FALLBACK_TABLE = "facturas"

    def __init__(
        self,
        supabase: Any = _AUTO_SUPABASE,
        store: LocalStore | None = None,
        audit_service: AuditService | None = None,
        current_user: str = "sistema",
    ) -> None:
        self.supabase = get_supabase_client() if supabase is _AUTO_SUPABASE else supabase
        self.store = store or LocalStore()
        self.audit_service = audit_service or AuditService(self.store)
        self.current_user = current_user or "sistema"
        self.store.seed_bucket("productos", [self._producto_to_row(producto) for producto in SAMPLE_PRODUCTOS])

    def list_productos(self) -> list[Producto]:
        if self.supabase is not None:
            try:
                response = self.supabase.table(self.TABLE_NAME).select(
                    "id,nombre,descripcion,precio,tipo,categoria,activo"
                ).execute()
                rows = [self._map_producto(row) for row in response.data or []]
                if rows:
                    self.store.replace_bucket("productos", [self._producto_to_row(producto) for producto in rows])
                    return rows
            except Exception:
                try:
                    response = self.supabase.table(self.FACTURAS_FALLBACK_TABLE).select(
                        "id,tipo_factura,descripcion_general,descripcion_producto_servicio,cantidad,precio_unitario,importe_linea,subtotal_sin_iva"
                    ).execute()
                    return self._map_productos_desde_facturas(response.data or [])
                except Exception:
                    pass

        return [self._map_producto(row) for row in self.store.list_bucket("productos")]

    def get_producto(self, producto_id: str) -> Producto | None:
        for producto in self.list_productos():
            if producto.id == producto_id:
                return producto
        return None

    def count_productos(self) -> int:
        return len(self.list_productos())

    def list_categories(self) -> list[str]:
        return sorted({producto.categoria for producto in self.list_productos() if producto.categoria})

    def create_producto(self, payload: dict[str, Any]) -> Producto:
        nombre = str(payload.get("nombre", "")).strip()
        if not nombre:
            raise ValueError("El nombre del producto o servicio es obligatorio.")

        producto = Producto(
            id="",
            nombre=nombre,
            descripcion=str(payload.get("descripcion", "")).strip(),
            precio=Decimal(str(payload.get("precio", "0") or "0")),
            tipo=str(payload.get("tipo", "PRODUCTO")).strip().upper(),
            categoria=str(payload.get("categoria", "")).strip(),
            activo=bool(payload.get("activo", True)),
        )
        if producto.precio < 0:
            raise ValueError("El precio no puede ser negativo.")

        row = self.store.upsert("productos", self._producto_to_row(producto))
        self._sync_remote_create(row)
        result = self._map_producto(row)
        self.audit_service.record("producto", result.id, "create", f"Alta de producto {result.nombre}", self.current_user)
        return result

    def update_producto(self, producto_id: str, payload: dict[str, Any]) -> Producto:
        current = self.get_producto(producto_id)
        if current is None:
            raise ValueError("No se ha encontrado el producto seleccionado.")

        producto = Producto(
            id=producto_id,
            nombre=str(payload.get("nombre", current.nombre)).strip(),
            descripcion=str(payload.get("descripcion", current.descripcion)).strip(),
            precio=Decimal(str(payload.get("precio", current.precio) or "0")),
            tipo=str(payload.get("tipo", current.tipo)).strip().upper(),
            categoria=str(payload.get("categoria", current.categoria)).strip(),
            activo=bool(payload.get("activo", current.activo)),
        )
        if not producto.nombre:
            raise ValueError("El nombre del producto o servicio es obligatorio.")

        row = self.store.upsert("productos", self._producto_to_row(producto), row_id=producto_id)
        self._sync_remote_update(row)
        result = self._map_producto(row)
        self.audit_service.record("producto", result.id, "update", f"Actualización de producto {result.nombre}", self.current_user)
        return result

    def delete_producto(self, producto_id: str) -> None:
        current = self.get_producto(producto_id)
        if current is None:
            raise ValueError("No se ha encontrado el producto seleccionado.")

        self.store.delete("productos", producto_id)
        self._sync_remote_delete(producto_id)
        self.audit_service.record("producto", producto_id, "delete", f"Baja de producto {current.nombre}", self.current_user)

    def _sync_remote_create(self, row: dict[str, Any]) -> None:
        if self.supabase is None:
            return
        try:
            self.supabase.table(self.TABLE_NAME).insert(row).execute()
        except Exception:
            return

    def _sync_remote_update(self, row: dict[str, Any]) -> None:
        if self.supabase is None:
            return
        try:
            self.supabase.table(self.TABLE_NAME).update(row).eq("id", row["id"]).execute()
        except Exception:
            return

    def _sync_remote_delete(self, producto_id: str) -> None:
        if self.supabase is None:
            return
        try:
            self.supabase.table(self.TABLE_NAME).delete().eq("id", producto_id).execute()
        except Exception:
            return

    @staticmethod
    def _map_productos_desde_facturas(rows: list[dict[str, Any]]) -> list[Producto]:
        productos: list[Producto] = []
        seen: set[tuple[str, Decimal]] = set()

        for row in rows:
            nombre = str(
                row.get("descripcion_producto_servicio")
                or row.get("descripcion_general")
                or row.get("tipo_factura")
                or ""
            ).strip()
            if not nombre:
                continue

            precio = _precio_desde_factura(row)
            key = (nombre.lower(), precio)
            if key in seen:
                continue

            seen.add(key)
            productos.append(
                Producto(
                    id=f"factura-{row.get('id', '')}",
                    nombre=nombre,
                    descripcion=str(row.get("descripcion_general") or nombre),
                    precio=precio,
                    tipo=_tipo_desde_factura(row),
                    categoria="Derivado",
                )
            )

        return productos

    @staticmethod
    def _map_producto(row: dict[str, Any]) -> Producto:
        return Producto(
            id=str(row.get("id", "")),
            nombre=str(row.get("nombre", "")),
            descripcion=str(row.get("descripcion", "")),
            precio=Decimal(str(row.get("precio", "0") or "0")),
            tipo=str(row.get("tipo", "PRODUCTO") or "PRODUCTO"),
            categoria=str(row.get("categoria", "")),
            activo=bool(row.get("activo", True)),
        )

    @staticmethod
    def _producto_to_row(producto: Producto) -> dict[str, Any]:
        row = asdict(producto)
        row["precio"] = str(producto.precio)
        return row


def _precio_desde_factura(row: dict[str, Any]) -> Decimal:
    if row.get("precio_unitario") is not None:
        return Decimal(str(row.get("precio_unitario")))

    cantidad = Decimal(str(row.get("cantidad") or "1"))
    if row.get("importe_linea") is not None and cantidad:
        return Decimal(str(row.get("importe_linea"))) / cantidad

    return Decimal(str(row.get("subtotal_sin_iva") or "0"))


def _tipo_desde_factura(row: dict[str, Any]) -> str:
    text = f"{row.get('tipo_factura', '')} {row.get('descripcion_producto_servicio', '')}".lower()
    if "servicio" in text:
        return "SERVICIO"
    return "PRODUCTO"
