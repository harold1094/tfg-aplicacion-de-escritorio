"""Copias de seguridad locales del modo escritorio."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from shutil import copy2, make_archive

from app.config import get_settings


class BackupService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.settings.backups_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_dir = self.settings.backups_dir / f"backup_{timestamp}"
        target_dir.mkdir(parents=True, exist_ok=True)

        copy2(self.settings.local_data_file, target_dir / self.settings.local_data_file.name)
        if self.settings.attachments_dir.exists():
            archive_base = target_dir / "attachments"
            make_archive(str(archive_base), "zip", root_dir=self.settings.attachments_dir)

        return target_dir
