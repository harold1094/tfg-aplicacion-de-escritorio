"""Controlador de clientes."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.models.cliente import Cliente
from app.services.audit_service import AuditService
from app.services.local_store import LocalStore
from app.supabase_client import get_supabase_client

_AUTO_SUPABASE = object()


SAMPLE_CLIENTES = [
    Cliente("1", "Clínica Norte", "administracion@clinicanorte.es", "910 000 001", "B00000001", "Madrid"),
    Cliente("2", "Arquitectura Rivas", "facturacion@rivas.es", "910 000 002", "B00000002", "Toledo"),
    Cliente("3", "Talleres Centro", "compras@tallerescentro.es", "910 000 003", "B00000003", "Valencia"),
]


class ClienteController:
    TABLE_NAME = "clientesEmisor"

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
        self.store.seed_bucket("clientes", [self._cliente_to_row(cliente) for cliente in SAMPLE_CLIENTES])

    def list_clientes(self) -> list[Cliente]:
        if self.supabase is not None:
            try:
                response = self.supabase.table(self.TABLE_NAME).select(
                    "id,nombre,cif_nif_nie,direccion_completa,correo_electronico,telefono"
                ).execute()
                rows = [self._map_cliente(row) for row in response.data or []]
                if rows:
                    self.store.replace_bucket("clientes", [self._cliente_to_row(cliente) for cliente in rows])
                    return rows
            except Exception:
                pass

        return [self._map_cliente(row) for row in self.store.list_bucket("clientes")]

    def get_cliente(self, cliente_id: str) -> Cliente | None:
        for cliente in self.list_clientes():
            if cliente.id == cliente_id:
                return cliente
        return None

    def count_clientes(self) -> int:
        return len(self.list_clientes())

    def create_cliente(self, payload: dict[str, Any]) -> Cliente:
        nombre = str(payload.get("nombre", "")).strip()
        if not nombre:
            raise ValueError("El nombre del cliente es obligatorio.")

        cliente = Cliente(
            id="",
            nombre=nombre,
            email=str(payload.get("email", "")).strip(),
            telefono=str(payload.get("telefono", "")).strip(),
            nif=str(payload.get("nif", "")).strip(),
            direccion=str(payload.get("direccion", "")).strip(),
            activo=bool(payload.get("activo", True)),
        )

        row = self._cliente_to_row(cliente)
        stored_row = self.store.upsert("clientes", row)
        self._sync_remote_create(stored_row)
        result = self._map_cliente(stored_row)
        self.audit_service.record("cliente", result.id, "create", f"Alta de cliente {result.nombre}", self.current_user)
        return result

    def update_cliente(self, cliente_id: str, payload: dict[str, Any]) -> Cliente:
        current = self.get_cliente(cliente_id)
        if current is None:
            raise ValueError("No se ha encontrado el cliente seleccionado.")

        updated = Cliente(
            id=cliente_id,
            nombre=str(payload.get("nombre", current.nombre)).strip(),
            email=str(payload.get("email", current.email)).strip(),
            telefono=str(payload.get("telefono", current.telefono)).strip(),
            nif=str(payload.get("nif", current.nif)).strip(),
            direccion=str(payload.get("direccion", current.direccion)).strip(),
            activo=bool(payload.get("activo", current.activo)),
        )
        if not updated.nombre:
            raise ValueError("El nombre del cliente es obligatorio.")

        row = self.store.upsert("clientes", self._cliente_to_row(updated), row_id=cliente_id)
        self._sync_remote_update(row)
        result = self._map_cliente(row)
        self.audit_service.record("cliente", result.id, "update", f"Actualización de cliente {result.nombre}", self.current_user)
        return result

    def delete_cliente(self, cliente_id: str) -> None:
        current = self.get_cliente(cliente_id)
        if current is None:
            raise ValueError("No se ha encontrado el cliente seleccionado.")

        self.store.delete("clientes", cliente_id)
        self._sync_remote_delete(cliente_id)
        self.audit_service.record("cliente", cliente_id, "delete", f"Baja de cliente {current.nombre}", self.current_user)

    def _sync_remote_create(self, row: dict[str, Any]) -> None:
        if self.supabase is None:
            return
        payload = {
            "nombre": row["nombre"],
            "cif_nif_nie": row["nif"],
            "direccion_completa": row["direccion"],
            "correo_electronico": row["email"],
            "telefono": row["telefono"],
        }
        try:
            self.supabase.table(self.TABLE_NAME).insert(payload).execute()
        except Exception:
            return

    def _sync_remote_update(self, row: dict[str, Any]) -> None:
        if self.supabase is None or not row.get("id"):
            return
        payload = {
            "nombre": row["nombre"],
            "cif_nif_nie": row["nif"],
            "direccion_completa": row["direccion"],
            "correo_electronico": row["email"],
            "telefono": row["telefono"],
        }
        try:
            self.supabase.table(self.TABLE_NAME).update(payload).eq("id", row["id"]).execute()
        except Exception:
            return

    def _sync_remote_delete(self, cliente_id: str) -> None:
        if self.supabase is None:
            return
        try:
            self.supabase.table(self.TABLE_NAME).delete().eq("id", cliente_id).execute()
        except Exception:
            return

    @staticmethod
    def _map_cliente(row: dict[str, Any]) -> Cliente:
        return Cliente(
            id=str(row.get("id", "")),
            nombre=str(row.get("nombre", "")),
            email=str(row.get("correo_electronico", row.get("email", ""))),
            telefono=str(row.get("telefono", "")),
            nif=str(row.get("cif_nif_nie", row.get("nif", ""))),
            direccion=str(row.get("direccion_completa", row.get("direccion", ""))),
            activo=bool(row.get("activo", True)),
        )

    @staticmethod
    def _cliente_to_row(cliente: Cliente) -> dict[str, Any]:
        row = asdict(cliente)
        row["correo_electronico"] = row["email"]
        row["cif_nif_nie"] = row["nif"]
        row["direccion_completa"] = row["direccion"]
        return row
