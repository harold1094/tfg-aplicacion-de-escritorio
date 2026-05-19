"""Modelos de dominio de la aplicación."""

from app.models.auditoria import AuditEntry
from app.models.cliente import Cliente
from app.models.factura import AdjuntoFactura, EstadoFactura, Factura, LineaFactura
from app.models.producto import Producto
from app.models.security import UserPermissions, UserRole, permissions_for_role

__all__ = [
    "AdjuntoFactura",
    "AuditEntry",
    "Cliente",
    "EstadoFactura",
    "Factura",
    "LineaFactura",
    "Producto",
    "UserPermissions",
    "UserRole",
    "permissions_for_role",
]
