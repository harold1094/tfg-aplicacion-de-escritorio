"""Exportación PDF usando Qt."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFont, QPainter, QPageSize, QPdfWriter


def _stringify(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return "" if value is None else str(value)


def export_rows_to_pdf(
    rows: Iterable[Mapping[str, Any]],
    file_path: str | Path,
    title: str = "Informe de facturación",
    fieldnames: list[str] | None = None,
) -> Path:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    row_list = list(rows)

    if fieldnames is None:
        fieldnames = list(row_list[0].keys()) if row_list else []

    writer = QPdfWriter(str(path))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setResolution(120)

    painter = QPainter(writer)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    title_font = QFont("Segoe UI", 16, QFont.Weight.Bold)
    body_font = QFont("Segoe UI", 9)
    header_font = QFont("Segoe UI", 9, QFont.Weight.Bold)

    page_width = writer.width()
    page_height = writer.height()
    left = 80
    top = 80
    line_height = 30

    painter.setFont(title_font)
    painter.drawText(QRect(left, top, page_width - 2 * left, 40), Qt.AlignmentFlag.AlignLeft, title)
    y = top + 70

    painter.setFont(header_font)
    header_text = " | ".join(fieldnames)
    painter.drawText(QRect(left, y, page_width - 2 * left, line_height), Qt.AlignmentFlag.AlignLeft, header_text)
    y += line_height + 10

    painter.setFont(body_font)
    for row in row_list:
        values = " | ".join(_stringify(row.get(field, "")) for field in fieldnames)
        painter.drawText(QRect(left, y, page_width - 2 * left, line_height * 2), Qt.TextWordWrap, values)
        y += line_height * 2
        if y > page_height - 100:
            writer.newPage()
            y = top
            painter.setFont(body_font)

    painter.end()
    return path
