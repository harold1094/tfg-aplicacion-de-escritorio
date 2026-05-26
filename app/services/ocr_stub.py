"""Punto de integración para OCR.

El OCR real queda pendiente por decisión de alcance. Este servicio mantiene el
flujo y la interfaz preparados para que otra persona implemente la extracción.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class OcrDraft:
    source_path: Path
    cliente_nombre: str
    descripcion: str
    status: str = "pendiente_ocr"


class OcrStubService:
    def prepare_import(self, file_path: str | Path) -> OcrDraft:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(path)

        return OcrDraft(
            source_path=path,
            cliente_nombre=path.stem.replace("_", " ").replace("-", " ").title() or "Cliente importado",
            descripcion=f"Importacion pendiente de OCR desde {path.name}",
        )
