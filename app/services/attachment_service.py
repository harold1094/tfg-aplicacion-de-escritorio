"""Gestión de adjuntos de factura en almacenamiento local."""

from __future__ import annotations

import hashlib
import mimetypes
from datetime import datetime
from pathlib import Path
from shutil import copy2
from uuid import uuid4

from app.config import get_settings
from app.models.factura import AdjuntoFactura
from app.supabase_client import get_supabase_client


class AttachmentService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.supabase = get_supabase_client()

    def attach_file(self, invoice_id: str, source_path: str | Path) -> AdjuntoFactura:
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"No existe el archivo seleccionado: {source}")

        target_dir = self.settings.attachments_dir / invoice_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_name = f"{uuid4()}_{source.name}"
        target = target_dir / target_name
        copy2(source, target)

        mime_type, _ = mimetypes.guess_type(target.name)
        remote_url = ""
        remote_url = self._try_upload_remote(invoice_id, target)

        return AdjuntoFactura(
            id=str(uuid4()),
            nombre_archivo=source.name,
            ruta=str(target),
            remote_url=remote_url,
            tipo_mime=mime_type or "application/octet-stream",
            tamano_bytes=target.stat().st_size,
            sha256=self._sha256(target),
            fecha_registro=datetime.now().isoformat(timespec="seconds"),
        )

    @staticmethod
    def _sha256(file_path: Path) -> str:
        digest = hashlib.sha256()
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _try_upload_remote(self, invoice_id: str, file_path: Path) -> str:
        if self.supabase is None:
            return ""

        bucket = "facturas"
        object_name = f"{invoice_id}/{file_path.name}"
        try:
            with file_path.open("rb") as handle:
                self.supabase.storage.from_(bucket).upload(object_name, handle.read(), {"upsert": "true"})
            return self.supabase.storage.from_(bucket).get_public_url(object_name)
        except Exception:
            return ""
