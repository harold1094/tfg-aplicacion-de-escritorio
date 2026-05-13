"""Controlador de productos y servicios."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.models.producto import Producto
from app.supabase_client import get_supabase_client


SAMPLE_PRODUCTOS = [
    Producto("1", "Diseño web corporativo", "Servicio de diseño y maquetación inicial", Decimal("850.00"), "SERVICIO"),
    Producto("2", "Mantenimiento mensual", "Soporte técnico y actualizaciones", Decimal("120.00"), "SERVICIO"),
    Producto("3", "Licencia software", "Licencia anual de herramienta de gestión", Decimal("299.00"), "PRODUCTO"),
]


class ProductoController:
    # En el esquema recibido no existe una tabla independiente de catálogo.
    # De momento se derivan productos/servicios desde las líneas guardadas en facturas.
    TABLE_NAME = "facturas"

    def __init__(self, supabase: Any | None = None) -> None:
        self.supabase = supabase if supabase is not None else get_supabase_client()

    def list_productos(self) -> list[Producto]:
        """Lista productos/servicios en modo solo lectura.

        Cuando exista una tabla real de catálogo, este controlador será el punto
        donde cambiar el origen de datos sin tocar las vistas.
        """

        if self.supabase is None:
            return SAMPLE_PRODUCTOS

        try:
            response = self.supabase.table(self.TABLE_NAME).select(
                "id,tipo_factura,descripcion_general,descripcion_producto_servicio,cantidad,precio_unitario,importe_linea,subtotal_sin_iva"
            ).execute()
            return self._map_productos_desde_facturas(response.data or [])
        except Exception:
            return SAMPLE_PRODUCTOS

    def count_productos(self) -> int:
        return len(self.list_productos())

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
                )
            )

        return productos


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
