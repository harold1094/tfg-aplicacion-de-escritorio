"""Exportación a CSV."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Mapping


def _stringify(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return "" if value is None else str(value)


def export_rows_to_csv(
    rows: Iterable[Mapping[str, Any]],
    file_path: str | Path,
    fieldnames: list[str] | None = None,
) -> Path:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    row_list = list(rows)

    if fieldnames is None:
        fieldnames = list(row_list[0].keys()) if row_list else []

    with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in row_list:
            writer.writerow({field: _stringify(row.get(field, "")) for field in fieldnames})

    return path

