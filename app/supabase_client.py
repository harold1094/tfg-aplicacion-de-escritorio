"""Cliente de Supabase.

Este módulo solo prepara la conexión. No crea tablas, no modifica esquemas y no
ejecuta operaciones destructivas.
"""

from __future__ import annotations

from typing import Any

from app.config import get_settings

try:
    from supabase import Client, create_client
except ImportError:  # pragma: no cover - depende de instalación local
    Client = Any  # type: ignore
    create_client = None  # type: ignore


_client: Client | None = None


def get_supabase_client() -> Client | None:
    """Devuelve un cliente de Supabase si el entorno está configurado."""

    global _client

    settings = get_settings()
    if not settings.supabase_configured or create_client is None:
        return None

    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_key)

    return _client

