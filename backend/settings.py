"""Központi, szerveroldali konfiguráció.

Titkot soha nem ad vissza API-válaszban, és nem enged kliensoldali
NEXT_PUBLIC_* név alatt szerverjogosultságú kulcsot használni.
"""

from dataclasses import dataclass
from functools import lru_cache
import os

from dotenv import load_dotenv

load_dotenv()


def _csv(name: str, default: str) -> tuple[str, ...]:
    value = os.getenv(name, default)
    return tuple(item.strip().rstrip("/") for item in value.split(",") if item.strip())


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"A(z) {name} csak egész szám lehet.") from exc
    if value <= 0:
        raise RuntimeError(f"A(z) {name} csak pozitív szám lehet.")
    return value


@dataclass(frozen=True)
class Settings:
    app_env: str
    supabase_url: str
    supabase_publishable_key: str
    supabase_secret_key: str
    cors_origins: tuple[str, ...]
    max_json_bytes: int
    max_upload_bytes: int
    api_requests_per_minute: int
    ai_requests_per_minute: int
    auth_requests_per_minute: int

    @property
    def production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def auth_ready(self) -> bool:
        return bool(self.supabase_url and self.supabase_publishable_key)

    @property
    def database_ready(self) -> bool:
        return bool(self.supabase_url and self.supabase_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        supabase_url=os.getenv("SUPABASE_URL", "").rstrip("/"),
        supabase_publishable_key=(
            os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
            or os.getenv("SUPABASE_ANON_KEY", "")
        ),
        supabase_secret_key=(
            os.getenv("SUPABASE_SECRET_KEY", "")
            or os.getenv("SUPABASE_SERVICE_KEY", "")
        ),
        cors_origins=_csv(
            "ALLOWED_ORIGINS",
            "https://ats-career-agent-z3od.vercel.app,http://localhost:3000",
        ),
        max_json_bytes=_positive_int("MAX_JSON_BYTES", 2 * 1024 * 1024),
        max_upload_bytes=_positive_int("MAX_UPLOAD_BYTES", 5 * 1024 * 1024),
        api_requests_per_minute=_positive_int("API_REQUESTS_PER_MINUTE", 60),
        ai_requests_per_minute=_positive_int("AI_REQUESTS_PER_MINUTE", 12),
        auth_requests_per_minute=_positive_int("AUTH_REQUESTS_PER_MINUTE", 8),
    )
