"""Modelo de producto o servicio."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True)
class Producto:
    id: str
    nombre: str
    descripcion: str
    precio: Decimal
    tipo: str = "PRODUCTO"
    categoria: str = ""
    activo: bool = True
