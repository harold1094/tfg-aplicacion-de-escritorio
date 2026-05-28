"""Backward-compatible import for the real OCR service."""

from __future__ import annotations

from app.services.ocr_service import OcrDraft, OcrService


OcrStubService = OcrService

__all__ = ["OcrDraft", "OcrService", "OcrStubService"]
