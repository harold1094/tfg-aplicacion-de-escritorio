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
class Factura:
    id: str
    numero: str
    cliente_nombre: str
    fecha: date
    estado: EstadoFactura
    lineas: list[LineaFactura] = field(default_factory=list)
    importe_pagado: Decimal = Decimal("0.00")
    cliente_id: str = ""
    cliente_nif: str = ""
    cliente_email: str = ""
    cliente_direccion: str = ""
    notas: str = ""
    serie: str = "FAC"
    numero_factura: int | None = None
    verifactu_uuid: str = ""
    verifactu_url: str = ""
    verifactu_qr: str = ""

    @property
    def editable(self) -> bool:
        return self.estado.editable

