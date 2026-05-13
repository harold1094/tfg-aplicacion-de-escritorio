"""Exportación a XML."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping
from xml.etree import ElementTree as ET


def _stringify(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return "" if value is None else str(value)


def export_rows_to_xml(
    rows: Iterable[Mapping[str, Any]],
    file_path: str | Path,
    root_name: str = "facturas",
    item_name: str = "factura",
) -> Path:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    root = ET.Element(root_name)
    for row in rows:
        item = ET.SubElement(root, item_name)
        for key, value in row.items():
            child = ET.SubElement(item, key)
            child.text = _stringify(value)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path

