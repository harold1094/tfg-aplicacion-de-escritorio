"""Controlador de clientes."""

from __future__ import annotations

from typing import Any

from app.models.cliente import Cliente
from app.supabase_client import get_supabase_client


SAMPLE_CLIENTES = [
    Cliente("1", "Clínica Norte", "administracion@clinicanorte.es", "910 000 001", "B00000001", "Madrid"),
    Cliente("2", "Arquitectura Rivas", "facturacion@rivas.es", "910 000 002", "B00000002", "Toledo"),
    Cliente("3", "Talleres Centro", "compras@tallerescentro.es", "910 000 003", "B00000003", "Valencia"),
]


class ClienteController:
    # Tabla real recibida del esquema. No usar public.cliente porque contiene password.
    TABLE_NAME = "clientesEmisor"

    def __init__(self, supabase: Any | None = None, emisor_id: str = "") -> None:
        self.supabase = supabase if supabase is not None else get_supabase_client()
        self.emisor_id = str(emisor_id or "")

    def list_clientes(self) -> list[Cliente]:
        """Lista clientes en modo solo lectura.

        Hasta validar el esquema real, la aplicación usa datos de muestra si
        Supabase no está configurado o si la consulta no puede mapearse.
        """

        if self.supabase is None:
            return SAMPLE_CLIENTES
        if not self.emisor_id:
            return []

        try:
            response = self.supabase.table(self.TABLE_NAME).select(
                "id,nombre,cif_nif_nie,direccion_completa,correo_electronico,telefono"
            ).execute()
            return [self._map_cliente(row) for row in response.data or []]
        except Exception:
            return []

    def count_clientes(self) -> int:
        return len(self.list_clientes())

    def create_cliente(self, cliente: Cliente) -> Cliente:
        if self.supabase is None:
            raise RuntimeError("Supabase no está configurado")

        payload = {
            "nombre": cliente.nombre,
            "correo_electronico": cliente.email or None,
            "telefono": cliente.telefono or None,
            "cif_nif_nie": cliente.nif or None,
            "direccion_completa": cliente.direccion or None,
        }
        response = self.supabase.table(self.TABLE_NAME).insert(payload).execute()
        return self._map_cliente(response.data[0])

    def update_cliente(self, cliente: Cliente) -> Cliente:
        if self.supabase is None:
            raise RuntimeError("Supabase no está configurado")

        payload = {
            "nombre": cliente.nombre,
            "correo_electronico": cliente.email or None,
            "telefono": cliente.telefono or None,
            "cif_nif_nie": cliente.nif or None,
            "direccion_completa": cliente.direccion or None,
        }
        response = self.supabase.table(self.TABLE_NAME).update(payload).eq("id", cliente.id).execute()
        return self._map_cliente(response.data[0])

    def delete_cliente(self, cliente_id: str) -> None:
        if self.supabase is None:
            raise RuntimeError("Supabase no está configurado")
        self.supabase.table(self.TABLE_NAME).delete().eq("id", cliente_id).execute()

    @staticmethod
    def _map_cliente(row: dict[str, Any]) -> Cliente:
        return Cliente(
            id=str(row.get("id", "")),
            nombre=str(row.get("nombre", "")),
            email=str(row.get("correo_electronico", "")),
            telefono=str(row.get("telefono", "")),
            nif=str(row.get("cif_nif_nie", "")),
            direccion=str(row.get("direccion_completa", "")),
        )
