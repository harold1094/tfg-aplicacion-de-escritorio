"""Modelos de auditoría y actividad."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AuditEntry:
    id: str
    entity_type: str
    entity_id: str
    action: str
    description: str
    user_email: str
    created_at: str
