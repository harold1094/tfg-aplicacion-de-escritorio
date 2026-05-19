"""Registro de actividad de usuario."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.models.auditoria import AuditEntry
from app.services.local_store import LocalStore


class AuditService:
    def __init__(self, store: LocalStore | None = None) -> None:
        self.store = store or LocalStore()

    def record(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        description: str,
        user_email: str = "sistema",
    ) -> AuditEntry:
        entry = AuditEntry(
            id=str(uuid4()),
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            description=description,
            user_email=user_email or "sistema",
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
        rows = self.store.list_bucket("audit_logs")
        rows.insert(0, asdict(entry))
        self.store.replace_bucket("audit_logs", rows[:500])
        return entry

    def list_entries(self, limit: int | None = None) -> list[AuditEntry]:
        rows = self.store.list_bucket("audit_logs")
        if limit is not None:
            rows = rows[:limit]
        return [AuditEntry(**row) for row in rows]

    def summary(self) -> dict[str, Any]:
        rows = self.list_entries(limit=20)
        return {
            "recent_count": len(rows),
            "latest_action": rows[0].action if rows else "",
        }
