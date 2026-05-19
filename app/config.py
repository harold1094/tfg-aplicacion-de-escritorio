"""Configuración central de la aplicación."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
DATA_DIR = BASE_DIR / "data"
ATTACHMENTS_DIR = DATA_DIR / "attachments"
EXPORTS_DIR = DATA_DIR / "exports"

load_dotenv(ENV_PATH)


@dataclass(frozen=True)
class Settings:
    """Valores de configuración cargados desde variables de entorno."""

    supabase_url: str = os.getenv("SUPABASE_URL", "").strip()
    supabase_key: str = os.getenv("SUPABASE_KEY", "").strip()
    smtp_host: str = os.getenv("SMTP_HOST", "").strip()
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password: str = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_sender: str = os.getenv("SMTP_SENDER", "").strip()
    admin_emails: tuple[str, ...] = tuple(
        item.strip().lower() for item in os.getenv("ADMIN_EMAILS", "").split(",") if item.strip()
    )
    accountant_emails: tuple[str, ...] = tuple(
        item.strip().lower() for item in os.getenv("ACCOUNTANT_EMAILS", "").split(",") if item.strip()
    )
    local_data_file: Path = DATA_DIR / "desktop_data.json"
    attachments_dir: Path = ATTACHMENTS_DIR
    exports_dir: Path = EXPORTS_DIR
    backups_dir: Path = DATA_DIR / "backups"

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    @property
    def smtp_configured(self) -> bool:
        return bool(
            self.smtp_host
            and self.smtp_port
            and self.smtp_username
            and self.smtp_password
            and self.smtp_sender
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()
