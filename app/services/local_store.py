"""Persistencia local JSON para modo escritorio."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import get_settings


DEFAULT_DATA = {
    "clientes": [],
    "productos": [],
    "facturas": [],
    "audit_logs": [],
}


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Tipo no serializable: {type(value)!r}")


class LocalStore:
    def __init__(self, file_path: Path | None = None) -> None:
        settings = get_settings()
        self.file_path = file_path or settings.local_data_file
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.write(DEFAULT_DATA)

    def read(self) -> dict[str, Any]:
        with self.file_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        merged = deepcopy(DEFAULT_DATA)
        merged.update(data)
        return merged

    def write(self, data: dict[str, Any]) -> None:
        payload = deepcopy(DEFAULT_DATA)
        payload.update(data)
        with self.file_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=_json_default)

    def list_bucket(self, bucket: str) -> list[dict[str, Any]]:
        return list(self.read().get(bucket, []))

    def replace_bucket(self, bucket: str, rows: list[dict[str, Any]]) -> None:
        data = self.read()
        data[bucket] = rows
        self.write(data)

    def seed_bucket(self, bucket: str, rows: list[dict[str, Any]]) -> None:
        current = self.list_bucket(bucket)
        if current:
            return
        self.replace_bucket(bucket, rows)

    def upsert(self, bucket: str, row: dict[str, Any], row_id: str | None = None) -> dict[str, Any]:
        data = self.read()
        rows = list(data.get(bucket, []))
        identifier = row_id or str(row.get("id") or uuid4())
        updated_row = dict(row)
        updated_row["id"] = identifier

        for index, current in enumerate(rows):
            if str(current.get("id")) == identifier:
                rows[index] = updated_row
                break
        else:
            rows.append(updated_row)

        data[bucket] = rows
        self.write(data)
        return updated_row

    def delete(self, bucket: str, row_id: str) -> None:
        data = self.read()
        data[bucket] = [row for row in data.get(bucket, []) if str(row.get("id")) != str(row_id)]
        self.write(data)
