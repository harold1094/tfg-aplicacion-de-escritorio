"""Controlador de autenticación con Supabase Auth."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings
from app.models.security import UserPermissions, UserRole, permissions_for_role
from app.services.role_service import RoleService
from app.supabase_client import get_supabase_client


@dataclass(frozen=True, slots=True)
class AuthUser:
    id: str
    email: str
    role: UserRole
    permissions: UserPermissions


@dataclass(frozen=True, slots=True)
class AuthResult:
    success: bool
    user: AuthUser | None = None
    error: str = ""


class AuthController:
    """Gestiona el inicio y cierre de sesión.

    Usa Supabase Auth. No consulta la tabla public.cliente ni maneja passwords
    directamente desde la aplicación.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.supabase = get_supabase_client()
        self.role_service = RoleService()

    def is_configured(self) -> bool:
        return self.settings.supabase_configured and self.supabase is not None

    def login(self, email: str, password: str) -> AuthResult:
        email = email.strip()
        if not email or not password:
            return AuthResult(False, error="Introduce email y contraseña.")

        if not self.is_configured():
            role = self.role_service.resolve_role(email)
            return AuthResult(
                True,
                user=AuthUser(
                    id=f"local::{email.lower()}",
                    email=email,
                    role=role,
                    permissions=self.role_service.permissions(email),
                ),
            )

        try:
            response = self.supabase.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
        except Exception as exc:
            return AuthResult(False, error=f"No se pudo iniciar sesión: {exc}")

        user = getattr(response, "user", None)
        if user is None:
            return AuthResult(False, error="Credenciales incorrectas o usuario no registrado.")

        role = self._resolve_remote_role(email)
        return AuthResult(
            True,
            user=AuthUser(
                id=str(getattr(user, "id", "")),
                email=str(getattr(user, "email", email)),
                role=role,
                permissions=permissions_for_role(role),
            ),
        )

    def logout(self) -> None:
        if self.supabase is None:
            return

        try:
            self.supabase.auth.sign_out()
        except Exception:
            return

    def _resolve_remote_role(self, email: str) -> UserRole:
        fallback = self.role_service.resolve_role(email)
        if self.supabase is None:
            return fallback

        try:
            response = self.supabase.table("roles_usuario").select("rol").eq("email", email).limit(1).execute()
            first = (response.data or [None])[0]
            role_value = str((first or {}).get("rol", "")).strip().lower()
            if role_value == UserRole.ADMINISTRADOR.value:
                return UserRole.ADMINISTRADOR
            if role_value == UserRole.CONTABLE.value:
                return UserRole.CONTABLE
        except Exception:
            return fallback

        return fallback
