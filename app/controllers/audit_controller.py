"""Controlador de auditoría."""

from __future__ import annotations

from app.models.auditoria import AuditEntry
from app.services.audit_service import AuditService


class AuditController:
    def __init__(self, audit_service: AuditService) -> None:
        self.audit_service = audit_service

    def list_entries(self, query: str = "") -> list[AuditEntry]:
        rows = self.audit_service.list_entries()
        needle = query.strip().lower()
        if not needle:
            return rows

        return [
            entry
            for entry in rows
            if needle in entry.action.lower()
            or needle in entry.entity_type.lower()
            or needle in entry.description.lower()
            or needle in entry.user_email.lower()
        ]
