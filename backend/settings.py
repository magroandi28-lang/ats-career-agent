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


def _choice(name: str, default: str, allowed: set[str]) -> str:
    value = os.getenv(name, default).strip().lower()
    if value not in allowed:
        options = ", ".join(sorted(allowed))
        raise RuntimeError(f"A(z) {name} értéke csak ez lehet: {options}.")
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
    ai_provider: str
    cv_ai_provider: str
    gemini_api_key: str
    openai_api_key: str
    gemini_flow_model: str
    openai_flow_model: str
    gemini_advisor_model: str
    openai_advisor_model: str
    gemini_writer_model: str
    openai_writer_model: str
    ai_timeout_seconds: int
    ai_max_steps_per_run: int
    ai_max_tool_calls_per_run: int

    @property
    def production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def auth_ready(self) -> bool:
        return bool(self.supabase_url and self.supabase_publishable_key)

    @property
    def database_ready(self) -> bool:
        return bool(self.supabase_url and self.supabase_secret_key)

    @property
    def ai_ready(self) -> bool:
        if self.ai_provider == "gemini":
            return bool(self.gemini_api_key)
        return bool(self.openai_api_key)

    def provider_for_task(self, task_type: str) -> str:
        """A CV-lánc külön szolgáltatón futhat a többi AI-feladattól."""
        if task_type in {"cv_analysis", "cv_writing", "cv_fact_check"}:
            return self.cv_ai_provider
        return self.ai_provider

    def model_for_task(self, task_type: str) -> str:
        """A feladat modelljét központilag választja ki.

        Az üzleti kód ezért nem függ közvetlenül egyik szolgáltatótól sem.
        """
        model_group = {
            "flow_routing": "flow",
            "career_advice": "advisor",
            "cv_analysis": "advisor",
            "cv_fact_check": "advisor",
            "cv_writing": "writer",
            "application_writing": "writer",
            "portfolio_writing": "writer",
        }.get(task_type, "flow")
        provider = self.provider_for_task(task_type)
        return getattr(self, f"{provider}_{model_group}_model")


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
        ai_provider=_choice("AI_PROVIDER", "gemini", {"gemini", "openai"}),
        cv_ai_provider=_choice(
            "CV_AI_PROVIDER", "openai", {"gemini", "openai"}
        ),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        gemini_flow_model=os.getenv("GEMINI_FLOW_MODEL", "gemini-2.5-flash"),
        openai_flow_model=os.getenv("OPENAI_FLOW_MODEL", "gpt-5.6-terra"),
        gemini_advisor_model=os.getenv("GEMINI_ADVISOR_MODEL", "gemini-2.5-pro"),
        openai_advisor_model=os.getenv("OPENAI_ADVISOR_MODEL", "gpt-5.6"),
        gemini_writer_model=os.getenv("GEMINI_WRITER_MODEL", "gemini-2.5-pro"),
        openai_writer_model=os.getenv("OPENAI_WRITER_MODEL", "gpt-5.6"),
        ai_timeout_seconds=_positive_int("AI_TIMEOUT_SECONDS", 90),
        ai_max_steps_per_run=_positive_int("AI_MAX_STEPS_PER_RUN", 8),
        ai_max_tool_calls_per_run=_positive_int("AI_MAX_TOOL_CALLS_PER_RUN", 5),
    )
