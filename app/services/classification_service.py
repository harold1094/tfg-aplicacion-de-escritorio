"""Clasificación asistida por reglas e histórico."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from app.models.factura import Factura
from app.models.producto import Producto


@dataclass(frozen=True, slots=True)
class ClassificationSuggestion:
    categoria: str
    proyecto: str
    reason: str


class ClassificationService:
    def suggest(
        self,
        cliente_nombre: str,
        line_descriptions: list[str],
        invoices: list[Factura],
        products: list[Producto],
    ) -> ClassificationSuggestion:
        client_matches = [invoice for invoice in invoices if invoice.cliente_nombre.lower() == cliente_nombre.lower()]
        categories = [invoice.categoria for invoice in client_matches if invoice.categoria]
        projects = [invoice.proyecto for invoice in client_matches if invoice.proyecto]

        if categories or projects:
            return ClassificationSuggestion(
                categoria=Counter(categories).most_common(1)[0][0] if categories else "",
                proyecto=Counter(projects).most_common(1)[0][0] if projects else "",
                reason="Sugerencia basada en el histórico del cliente.",
            )

        lowered_lines = " ".join(line_descriptions).lower()
        for product in products:
            if product.nombre.lower() in lowered_lines and product.categoria:
                return ClassificationSuggestion(
                    categoria=product.categoria,
                    proyecto="",
                    reason="Sugerencia basada en coincidencia con el catálogo.",
                )

        return ClassificationSuggestion("", "", "Sin suficientes datos históricos para sugerir clasificación.")
