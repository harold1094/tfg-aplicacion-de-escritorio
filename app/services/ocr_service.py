"""OCR and ticket/invoice parsing utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.models.factura import LineaFactura


EURO = "\u20ac"
DEFAULT_TAX_RATE = Decimal("0.21")


@dataclass(frozen=True, slots=True)
class OcrLineItem:
    description: str
    quantity: Decimal
    price: Decimal


@dataclass(frozen=True, slots=True)
class ParsedInvoiceText:
    vendor_name: str = ""
    vendor_nif: str = ""
    vendor_address: str = ""
    vendor_email: str = ""
    invoice_date: date = field(default_factory=date.today)
    total: Decimal = Decimal("0.00")
    subtotal: Decimal = Decimal("0.00")
    iva: Decimal = Decimal("0.00")
    iva_rate: Decimal = DEFAULT_TAX_RATE
    items: list[OcrLineItem] = field(default_factory=list)
    raw_text: str = ""


@dataclass(frozen=True, slots=True)
class OcrDraft:
    source_path: Path
    cliente_nombre: str
    descripcion: str
    fecha: date
    lineas: list[LineaFactura]
    cliente_nif: str = ""
    cliente_email: str = ""
    cliente_direccion: str = ""
    raw_text: str = ""
    status: str = "ocr_extraido"


class OcrService:
    """Extracts text from files and maps it to a reviewable invoice draft."""

    SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
    SUPPORTED_PDF_SUFFIXES = {".pdf"}
    SUPPORTED_TEXT_SUFFIXES = {".txt"}

    def prepare_import(self, file_path: str | Path) -> OcrDraft:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(path)

        raw_text = extract_text_from_file(path)
        parsed = parse_invoice_text(raw_text)
        cliente_nombre = parsed.vendor_name or _title_from_filename(path) or "Cliente importado"
        lineas = _build_invoice_lines(parsed, path)
        descripcion = _description_from_items(parsed.items, path)
        status = "ocr_extraido" if raw_text.strip() else "ocr_sin_texto"

        return OcrDraft(
            source_path=path,
            cliente_nombre=cliente_nombre,
            descripcion=descripcion,
            fecha=parsed.invoice_date,
            lineas=lineas,
            cliente_nif=parsed.vendor_nif,
            cliente_email=parsed.vendor_email,
            cliente_direccion=parsed.vendor_address,
            raw_text=raw_text,
            status=status,
        )


def extract_text_from_file(path: str | Path) -> str:
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix in OcrService.SUPPORTED_TEXT_SUFFIXES:
        return file_path.read_text(encoding="utf-8", errors="ignore").strip()

    if suffix in OcrService.SUPPORTED_PDF_SUFFIXES:
        return _extract_text_from_pdf(file_path)

    if suffix in OcrService.SUPPORTED_IMAGE_SUFFIXES:
        return _extract_text_from_image(file_path)

    raise ValueError("Formato no soportado. Usa PDF, TXT o una imagen.")


def _extract_text_from_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - depends on optional runtime deps
        raise RuntimeError("Falta la dependencia pypdf para leer PDFs.") from exc

    reader = PdfReader(str(path))
    page_texts = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(page_texts).strip()


def _extract_text_from_image(path: Path) -> str:
    try:
        from PIL import Image
        import pytesseract
    except ImportError as exc:  # pragma: no cover - depends on optional runtime deps
        raise RuntimeError("Faltan Pillow y pytesseract para OCR de imagenes.") from exc

    try:
        with Image.open(path) as image:
            return pytesseract.image_to_string(image, lang="spa+eng").strip()
    except pytesseract.TesseractNotFoundError as exc:  # pragma: no cover - local binary dependent
        raise RuntimeError(
            "Tesseract OCR no esta instalado o no esta en PATH. Instala Tesseract para leer imagenes."
        ) from exc
    except pytesseract.TesseractError as exc:  # pragma: no cover - local language data dependent
        raise RuntimeError("No se pudo ejecutar Tesseract OCR con los idiomas spa+eng.") from exc


def parse_invoice_text(text: str) -> ParsedInvoiceText:
    clean_text = _normalize_text(text)
    lines = [line.strip() for line in clean_text.splitlines() if line.strip()]

    return ParsedInvoiceText(
        vendor_name=_extract_vendor_name(lines),
        vendor_nif=_extract_nif(clean_text),
        vendor_address=_extract_address(lines),
        vendor_email=_extract_email(clean_text),
        invoice_date=_extract_date(clean_text),
        total=_extract_total(clean_text),
        subtotal=_extract_subtotal(clean_text),
        iva=_extract_iva(clean_text),
        iva_rate=_extract_iva_rate(clean_text),
        items=_extract_line_items(lines),
        raw_text=clean_text,
    )


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _extract_vendor_name(lines: list[str]) -> str:
    for line in lines[:5]:
        if len(line) < 3:
            continue
        if re.fullmatch(r"\d+[/.-]\d+[/.-]\d+", line):
            continue
        if re.fullmatch(r"[\d\s.,+\-*]+", line):
            continue
        if _is_summary_label(line):
            continue
        return line[:120]
    return ""


def _extract_nif(text: str) -> str:
    patterns = [
        r"\b([A-HJ-NP-SUVW]\d{7}[A-J0-9])\b",
        r"\b(\d{8}[A-Z])\b",
        r"\b([XYZKLM]\d{7}[A-Z])\b",
        r"(?:NIF|CIF|N\.I\.F|C\.I\.F)[:\s]*([A-Z0-9]{9})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return ""


def _extract_email(text: str) -> str:
    match = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, flags=re.IGNORECASE)
    return match.group(0) if match else ""


def _extract_address(lines: list[str]) -> str:
    keywords = ("C/", "CALLE", "AVDA", "AVENIDA", "PLAZA", "PL.", "CTRA", "CARRETERA", "VIA")
    for line in lines[:8]:
        upper = line.upper()
        if any(keyword in upper for keyword in keywords) or re.search(r"\b\d{5}\b", upper):
            return line[:200]
    return ""


def _extract_date(text: str) -> date:
    patterns = [
        r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})",
        r"(\d{1,2})[/-](\d{1,2})[/-](\d{2})\b",
        r"(\d{4})-(\d{2})-(\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        a, b, c = match.groups()
        if len(a) == 4:
            return _safe_date(int(a), int(b), int(c))
        year = int(c)
        if len(c) == 2:
            year += 1900 if year > 50 else 2000
        return _safe_date(year, int(b), int(a))
    return date.today()


def _extract_total(text: str) -> Decimal:
    patterns = [
        rf"TOTAL\s*(?:A\s*PAGAR)?[\s:{EURO}]*(\d+(?:[.,]\d{{2}}))",
        rf"IMPORTE\s*TOTAL[\s:{EURO}]*(\d+(?:[.,]\d{{2}}))",
        rf"TOTAL\s*FACTURA[\s:{EURO}]*(\d+(?:[.,]\d{{2}}))",
        rf"A\s*PAGAR[\s:{EURO}]*(\d+(?:[.,]\d{{2}}))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _parse_decimal(match.group(1))

    amounts = [_parse_decimal(match.group(1)) for match in re.finditer(r"(\d+(?:[.,]\d{2}))", text)]
    amounts = [amount for amount in amounts if amount > 0]
    return max(amounts) if amounts else Decimal("0.00")


def _extract_subtotal(text: str) -> Decimal:
    patterns = [
        rf"BASE\s*(?:IMPONIBLE)?[\s:{EURO}]*(\d+(?:[.,]\d{{2}}))",
        rf"SUBTOTAL[\s:{EURO}]*(\d+(?:[.,]\d{{2}}))",
        rf"NETO[\s:{EURO}]*(\d+(?:[.,]\d{{2}}))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _parse_decimal(match.group(1))
    return Decimal("0.00")


def _extract_iva(text: str) -> Decimal:
    patterns = [
        rf"IVA\s*(?:\d+\s*%)?[\s:{EURO}]*(\d+(?:[.,]\d{{2}}))",
        rf"I\.V\.A\.?\s*[\s:{EURO}]*(\d+(?:[.,]\d{{2}}))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _parse_decimal(match.group(1))
    return Decimal("0.00")


def _extract_iva_rate(text: str) -> Decimal:
    patterns = [
        r"IVA\s*(\d+)\s*%",
        r"I\.V\.A\.?\s*(\d+)\s*%",
        r"(\d+)\s*%\s*IVA",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _normalize_tax_rate(_parse_decimal(match.group(1)))
    return DEFAULT_TAX_RATE


def _extract_line_items(lines: list[str]) -> list[OcrLineItem]:
    items: list[OcrLineItem] = []
    price_pattern = re.compile(
        rf"^(.+?)\s+(\d+(?:[.,]\d+)?)\s*[xX*]\s*(\d+(?:[.,]\d{{2}}))\s*(?:{EURO}|EUR)?$",
        flags=re.IGNORECASE,
    )
    simple_price_pattern = re.compile(
        rf"^(.+?)\s+(\d+(?:[.,]\d{{2}}))\s*(?:{EURO}|EUR)?$",
        flags=re.IGNORECASE,
    )

    for line in lines:
        match = price_pattern.match(line)
        if match:
            description = match.group(1).strip()
            if description and not _is_summary_label(description):
                items.append(
                    OcrLineItem(
                        description=description[:200],
                        quantity=_parse_decimal(match.group(2)),
                        price=_parse_decimal(match.group(3)),
                    )
                )
            continue

        match = simple_price_pattern.match(line)
        if match:
            description = match.group(1).strip()
            if len(description) >= 2 and not _is_summary_label(description):
                items.append(
                    OcrLineItem(
                        description=description[:200],
                        quantity=Decimal("1"),
                        price=_parse_decimal(match.group(2)),
                    )
                )
    return items


def _build_invoice_lines(parsed: ParsedInvoiceText, path: Path) -> list[LineaFactura]:
    if parsed.items:
        return [
            LineaFactura(item.description, item.quantity, _money_decimal(item.price), parsed.iva_rate)
            for item in parsed.items
        ]

    description = _description_from_items(parsed.items, path)
    subtotal = parsed.subtotal
    if subtotal <= 0 and parsed.total > 0:
        subtotal = parsed.total / (Decimal("1") + parsed.iva_rate)
    price = _money_decimal(subtotal) if subtotal > 0 else Decimal("0.00")
    return [LineaFactura(description, Decimal("1"), price, parsed.iva_rate)]


def _description_from_items(items: list[OcrLineItem], path: Path) -> str:
    if items:
        return "; ".join(item.description for item in items)[:500]
    return f"Importado desde {path.name}"


def _title_from_filename(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").title()


def _parse_decimal(value: object) -> Decimal:
    text = str(value or "").strip().replace(EURO, "").replace("EUR", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def _normalize_tax_rate(value: Decimal) -> Decimal:
    if value > 1:
        return value / Decimal("100")
    return value


def _money_decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _safe_date(year: int, month: int, day: int) -> date:
    try:
        return date(year, month, day)
    except ValueError:
        return date.today()


def _is_summary_label(text: str) -> bool:
    return bool(
        re.match(
            r"^(TOTAL|BASE|IVA|I\.V\.A|SUBTOTAL|NETO|CAMBIO|EFECTIVO|TARJETA|VISA|MASTERCARD|A\s*PAGAR)\b",
            text.strip(),
            flags=re.IGNORECASE,
        )
    )
