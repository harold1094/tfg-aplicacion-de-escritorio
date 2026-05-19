"""Modelo de cliente."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Cliente:
    id: str
    nombre: str
    email: str = ""
    telefono: str = ""
    nif: str = ""
    direccion: str = ""
    activo: bool = True
