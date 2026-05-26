"""Autenticación de escritorio contra Supabase."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import get_settings
from app.supabase_client import get_supabase_client


@dataclass(frozen=True, slots=True)
class AuthSession:
    user_id: str
    email: str
    emisor_id: str = ""


class AuthService:
    """Capa mínima para no acoplar la UI a supabase-py."""

    def __init__(self, supabase: Any | None = None) -> None:
        self.settings = get_settings()
        self.supabase = supabase if supabase is not None else get_supabase_client()

    def is_configured(self) -> bool:
        return self.supabase is not None and self.settings.supabase_configured

    def login(self, email: str, password: str) -> AuthSession:
        if self.supabase is None:
            raise RuntimeError("Supabase no está configurado. Revisa SUPABASE_URL y SUPABASE_KEY.")
        if not email or not password:
            raise RuntimeError("Debes introducir email y contrasena.")

        try:
            response = self.supabase.auth.sign_in_with_password({"email": email, "password": password})
        except Exception as exc:
            message = str(exc).lower()
            if any(
                token in message
                for token in ("invalid login credentials", "email not confirmed", "invalid_credentials", "user not found")
            ):
                raise RuntimeError("No estas registrado o la contrasena es incorrecta.") from exc
            raise RuntimeError(f"No se pudo iniciar sesion en Supabase: {exc}") from exc
        user = getattr(response, "user", None)
        if user is None:
            raise RuntimeError("No estas registrado o la contrasena es incorrecta.")

        metadata = getattr(user, "user_metadata", None) or {}
        resolved_email = str(getattr(user, "email", email))
        emisor_id = str(metadata.get("id_emisor") or metadata.get("emisor_id") or "")
        if not emisor_id:
            emisor_id = self._resolve_emisor_id(resolved_email)

        return AuthSession(
            user_id=str(getattr(user, "id", "")),
            email=resolved_email,
            emisor_id=emisor_id,
        )

    def logout(self) -> None:
        if self.supabase is not None:
            self.supabase.auth.sign_out()

    def _resolve_emisor_id(self, email: str) -> str:
        """Busca un emisor razonable cuando el JWT no lleva id_emisor.

        Primero intenta vincular el usuario al emisor por correo de contacto.
        Si no existe vínculo, la autenticación sigue siendo válida, pero la app
        no cargará datos de un emisor hasta que exista esa relación.
        """

        if self.supabase is None or not email:
            return ""

        try:
            response = (
                self.supabase.table("emisores")
                .select("id,correo_contacto")
                .eq("correo_contacto", email)
                .limit(1)
                .execute()
            )
            if response.data:
                return str(response.data[0].get("id") or "")
        except Exception:
            return ""
        return ""
