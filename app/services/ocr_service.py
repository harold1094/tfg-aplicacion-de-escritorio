"""Extracción asistida desde nombre de archivo y texto legible."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True, slots=True)
class OCRAnalysis:
    provider_guess: str
    invoice_number: str
    invoice_date: str
    total_amount: Decimal | None
    warnings: list[str]


class OCRService:
    def analyze_document(self, file_path: str | Path) -> OCRAnalysis:
        path = Path(file_path)
        text = path.stem.replace("_", " ").replace("-", " ")
        warnings: list[str] = []

        if path.suffix.lower() in {".txt", ".csv", ".xml"}:
            try:
                text = f"{text} {path.read_text(encoding='utf-8', errors='ignore')[:2000]}"
            except OSError:
                warnings.append("No se pudo leer el contenido textual del archivo.")
        elif path.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg"}:
            warnings.append("Análisis heurístico: no hay un motor OCR externo configurado para lectura visual completa.")

        invoice_number = self._find_first(text, [r"(FAC[-\s]?\d{4}[-\s]?\d+)", r"(\d{4}[-/]\d{3,})"])
        invoice_date = self._find_first(text, [r"(\d{4}-\d{2}-\d{2})", r"(\d{2}[/-]\d{2}[/-]\d{4})"])
        amount_text = self._find_first(text, [r"(\d+[.,]\d{2})"])
        total_amount = Decimal(amount_text.replace(",", ".")) if amount_text else None

        provider_guess = path.stem.split("_")[0].split("-")[0].strip().title()
        if not provider_guess:
            provider_guess = "Proveedor desconocido"

        return OCRAnalysis(
            provider_guess=provider_guess,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            total_amount=total_amount,
            warnings=warnings,
        )

    @staticmethod
    def _find_first(text: str, patterns: list[str]) -> str:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""
