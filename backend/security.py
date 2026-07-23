"""Közös HTTP-, kvóta- és fájlbiztonsági segédek."""

from collections import defaultdict, deque
from hashlib import sha256
import re
from threading import Lock
import time
from uuid import uuid4

from fastapi import HTTPException, Request, UploadFile, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from backend.settings import get_settings


_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
_AI_PATHS = {
    "/szakma-felismeres",
    "/ats-diagnozis",
    "/cv-atiras",
    "/motivacios-level",
    "/flow-kiertekeles",
    "/flow-chat",
    "/ceginfo",
    "/skill-gap-elemzes",
    "/tanacsado-velemeny",
}


class RequestSecurityMiddleware(BaseHTTPMiddleware):
    """Korlátozza a deklarált kérésméretet és biztonsági headereket ad."""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        request_id = request.headers.get("x-request-id", "")
        if not _REQUEST_ID.fullmatch(request_id):
            request_id = str(uuid4())
        request.state.request_id = request_id

        content_length = request.headers.get("content-length")
        maximum = (
            settings.max_upload_bytes + 1024 * 1024
            if request.url.path == "/cv-feltoltes"
            else settings.max_json_bytes
        )
        if content_length:
            try:
                declared_size = int(content_length)
            except ValueError:
                return JSONResponse(
                    {"detail": "Érvénytelen Content-Length fejléc."},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            if declared_size > maximum:
                return JSONResponse(
                    {"detail": "A kérés túl nagy."},
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                )

        content_type = request.headers.get("content-type", "").lower()
        if (
            request.method in {"POST", "PUT", "PATCH"}
            and "application/json" in content_type
        ):
            body = await request.body()
            if len(body) > settings.max_json_bytes:
                return JSONResponse(
                    {"detail": "A kérés túl nagy."},
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["Cache-Control"] = (
            "no-store" if request.url.path.startswith("/auth/") else "private"
        )
        return response


class FixedWindowRateLimiter:
    """Egyfolyamatos Render-példányhoz biztonságos, memóriabeli limit.

    Több backend-példánynál ugyanez a szerződés közös Redis-tárra cserélendő.
    """

    def __init__(self):
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int, window_seconds: int = 60) -> int:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(window_seconds - (now - events[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Túl sok kérés. Próbáld újra később.",
                    headers={"Retry-After": str(retry_after)},
                )
            events.append(now)
        return limit - len(events)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


rate_limiter = FixedWindowRateLimiter()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def limit_auth_request(request: Request) -> None:
    settings = get_settings()
    rate_limiter.check(
        f"auth:{_client_ip(request)}",
        settings.auth_requests_per_minute,
    )


def limit_user_request(request: Request, user_id: str) -> None:
    settings = get_settings()
    limit = (
        settings.ai_requests_per_minute
        if request.url.path in _AI_PATHS
        else settings.api_requests_per_minute
    )
    identity_hash = sha256(user_id.encode("utf-8")).hexdigest()[:24]
    rate_limiter.check(f"user:{identity_hash}:{request.url.path}", limit)


async def read_validated_pdf(upload: UploadFile) -> bytes:
    """Méret-, MIME-, kiterjesztés- és magic-byte ellenőrzött PDF-olvasás."""

    settings = get_settings()
    filename = (upload.filename or "").lower()
    if upload.content_type != "application/pdf" or not filename.endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Csak valódi PDF-fájl tölthető fel.",
        )

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > settings.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="A fájl túl nagy (maximum 5 MB).",
            )
        chunks.append(chunk)

    content = b"".join(chunks)
    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A fájl tartalma nem érvényes PDF.",
        )
    return content
