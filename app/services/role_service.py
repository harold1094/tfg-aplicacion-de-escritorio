"""Resolución de roles y permisos de usuario."""

from __future__ import annotations

from app.config import get_settings
from app.models.security import UserPermissions, UserRole, permissions_for_role


class RoleService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def resolve_role(self, email: str) -> UserRole:
        normalized = email.strip().lower()
        if normalized in self.settings.admin_emails:
            return UserRole.ADMINISTRADOR
        if normalized in self.settings.accountant_emails:
            return UserRole.CONTABLE
        return UserRole.ADMINISTRADOR if not self.settings.admin_emails else UserRole.CONTABLE

    def permissions(self, email: str) -> UserPermissions:
        return permissions_for_role(self.resolve_role(email))
