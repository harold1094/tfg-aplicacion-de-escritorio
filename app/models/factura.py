"""Modelos relacionados con facturas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


class EstadoFactura(str, Enum):
    BORRADOR = "BORRADOR"
    EMITIDA = "EMITIDA"
    PAGADA = "PAGADA"
    PARCIALMENTE_PAGADA = "PARCIALMENTE_PAGADA"
    CANCELADA = "CANCELADA"

    @property
    def editable(self) -> bool:
        return self is EstadoFactura.BORRADOR


@dataclass(slots=True)
class LineaFactura:
    descripcion: str
    cantidad: Decimal
    precio_unitario: Decimal
    iva: Decimal = Decimal("0.21")


@dataclass(slots=True)
class AdjuntoFactura:
    id: str
    nombre_archivo: str
    ruta: str
    tipo_mime: str
    tamano_bytes: int
    sha256: str
    fecha_registro: str
    remote_url: str = ""


@dataclass(slots=True)
class Factura:
    id: str
    numero: str
    cliente_nombre: str
    fecha: date
    estado: EstadoFactura
    cliente_id: str = ""
    lineas: list[LineaFactura] = field(default_factory=list)
    importe_pagado: Decimal = Decimal("0.00")
    cliente_email: str = ""
    fecha_vencimiento: date | None = None
    categoria: str = ""
    proyecto: str = ""
    observaciones: str = ""
    adjuntos: list[AdjuntoFactura] = field(default_factory=list)

    @property
    def editable(self) -> bool:
        return self.estado.editable
