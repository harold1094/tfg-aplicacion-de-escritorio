"""Modelos de seguridad y sesión."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class UserRole(str, Enum):
    ADMINISTRADOR = "administrador"
    CONTABLE = "contable"


@dataclass(frozen=True, slots=True)
class UserPermissions:
    can_manage_master_data: bool
    can_delete_invoices: bool
    can_view_audit: bool
    can_send_email: bool


def permissions_for_role(role: UserRole) -> UserPermissions:
    if role is UserRole.ADMINISTRADOR:
        return UserPermissions(
            can_manage_master_data=True,
            can_delete_invoices=True,
            can_view_audit=True,
            can_send_email=True,
        )
    return UserPermissions(
        can_manage_master_data=False,
        can_delete_invoices=False,
        can_view_audit=False,
        can_send_email=True,
    )
