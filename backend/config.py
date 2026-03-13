from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class AppSettings:
    app_name: str
    app_version: str
    host: str
    port: int
    database_url: str
    cors_origins: list[str]
    log_level: str
    secret_key: str
    jwt_exp_minutes: int
    certificates_dir: Path
    public_base_url: str
    wipe_engine_dry_run: bool
    strict_database_startup: bool
    default_admin_username: str
    default_admin_password: str
    default_operator_username: str
    default_operator_password: str



def _as_bool(value: str, *, default: bool) -> bool:
    normalized = (value or "").strip().lower()
    if not normalized:
        return default
    return normalized in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    root_dir = Path(__file__).resolve().parents[1]
    certificates_dir = root_dir / "certificates"
    certificates_dir.mkdir(parents=True, exist_ok=True)
    default_sqlite_url = f"sqlite:///{(root_dir / 'cipherforge-dev.db').as_posix()}"

    cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:4200,http://localhost:4300")
    cors_origins = [origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()]

    return AppSettings(
        app_name="CipherForge Backend",
        app_version="2.0.0",
        host=os.getenv("BACKEND_HOST", "0.0.0.0"),
        port=int(os.getenv("BACKEND_PORT", "8000")),
        database_url=os.getenv("DATABASE_URL", default_sqlite_url),
        cors_origins=cors_origins,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        secret_key=os.getenv("JWT_SECRET_KEY", "cipherforge-dev-secret-key"),
        jwt_exp_minutes=int(os.getenv("JWT_EXP_MINUTES", "480")),
        certificates_dir=certificates_dir,
        public_base_url=os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"),
        wipe_engine_dry_run=_as_bool(os.getenv("WIPE_ENGINE_DRY_RUN", "true"), default=True),
        strict_database_startup=_as_bool(os.getenv("STRICT_DATABASE_STARTUP", "false"), default=False),
        default_admin_username=os.getenv("DEFAULT_ADMIN_USERNAME", "admin"),
        default_admin_password=os.getenv("DEFAULT_ADMIN_PASSWORD", "admin12345"),
        default_operator_username=os.getenv("DEFAULT_OPERATOR_USERNAME", "operator"),
        default_operator_password=os.getenv("DEFAULT_OPERATOR_PASSWORD", "operator12345"),
    )
