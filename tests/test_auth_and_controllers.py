from __future__ import annotations

from pathlib import Path

import app.controllers.auth_controller as auth_module
from app.config import get_settings
from app.controllers.auth_controller import AuthController
from app.controllers.cliente_controller import ClienteController
from app.controllers.factura_controller import FacturaController
from app.controllers.producto_controller import ProductoController
from app.services.audit_service import AuditService
from app.services.local_store import LocalStore


def build_store(tmp_path: Path) -> tuple[LocalStore, AuditService]:
    store = LocalStore(tmp_path / "desktop_data.json")
    audit = AuditService(store)
    return store, audit


def test_auth_controller_allows_local_login_without_supabase(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_KEY", "")
    get_settings.cache_clear()
    monkeypatch.setattr(auth_module, "get_supabase_client", lambda: None)

    controller = AuthController()
    result = controller.login("admin@example.com", "demo")

    assert result.success is True
    assert result.user is not None
    assert result.user.email == "admin@example.com"


def test_cliente_and_producto_crud_use_local_store(tmp_path):
    store, audit = build_store(tmp_path)
    clientes = ClienteController(supabase=None, store=store, audit_service=audit, current_user="admin@example.com")
    productos = ProductoController(supabase=None, store=store, audit_service=audit, current_user="admin@example.com")

    cliente = clientes.create_cliente({"nombre": "Nuevo Cliente", "email": "nuevo@example.com"})
    producto = productos.create_producto({"nombre": "Servicio", "descripcion": "Desc", "precio": "10.00"})

    assert clientes.get_cliente(cliente.id) is not None
    assert productos.get_producto(producto.id) is not None


def test_factura_controller_supports_create_payment_and_anomalies(tmp_path):
    store, audit = build_store(tmp_path)
    facturas = FacturaController(supabase=None, store=store, audit_service=audit, current_user="admin@example.com")

    factura = facturas.create_factura(
        {
            "numero": "FAC-TEST-1",
            "cliente_nombre": "Cliente Demo",
            "cliente_email": "cliente@example.com",
            "estado": "EMITIDA",
            "lineas": [{"descripcion": "Servicio", "cantidad": "1", "precio_unitario": "100.00", "iva": "0.21"}],
        }
    )
    updated = facturas.register_payment(factura.id, "50.00")
    anomalies = facturas.list_anomalies(factura.id)

    assert updated.importe_pagado == 50
    assert isinstance(anomalies, list)
