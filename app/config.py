"""Configuración central de la aplicación."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)


@dataclass(frozen=True)
class Settings:
    """Valores de configuración cargados desde variables de entorno."""

    supabase_url: str = os.getenv("SUPABASE_URL", "").strip()
    supabase_key: str = os.getenv("SUPABASE_KEY", "").strip()
    supabase_demo_email: str = os.getenv("SUPABASE_DEMO_EMAIL", "").strip()
    supabase_demo_password: str = os.getenv("SUPABASE_DEMO_PASSWORD", "").strip()

    smtp_host: str = os.getenv("SMTP_HOST", "").strip()
    smtp_port: int = int(os.getenv("SMTP_PORT", "587") or "587")
    smtp_user: str = os.getenv("SMTP_USER", "").strip()
    smtp_password: str = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from: str = os.getenv("SMTP_FROM", "").strip()
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "true").strip().lower() in {"1", "true", "yes", "on"}

    verifacti_api_base: str = os.getenv("VERIFACTI_API_BASE", "https://api.verifacti.com").strip()
    verifacti_api_key: str = os.getenv("VERIFACTI_API_KEY", "").strip()

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password and (self.smtp_from or self.smtp_user))

    @property
    def verifacti_configured(self) -> bool:
        return bool(self.verifacti_api_base and self.verifacti_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

