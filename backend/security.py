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
    "/api/v1/flow/messages",
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
            if request.url.path in {
                "/cv-feltoltes",
                "/api/v1/profile/import",
            }
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


def limit_guest_ai_request(request: Request) -> None:
    """Vendégmódú Flow-csevegés IP-alapú korlátja.

    Ugyanazt a szűk keretet kapja, mint a belépés/regisztráció: ez is
    bejelentkezés nélküli, modellhívást indító kérés, tehát közvetlenül
    a szolgáltatói kvótát terheli.
    """
    settings = get_settings()
    rate_limiter.check(
        f"guest_flow:{_client_ip(request)}",
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


# A CV-feltöltés elfogadott formátumai (folyamat_terkep.md 2. és 11.2).
#
# A kulcs a belső típusnév, amit a szövegkinyerés használ. Minden formátumnál
# HÁROM egyezésnek kell teljesülnie: kiterjesztés, MIME-típus és magic byte.
#
# A magic byte az EGYETLEN, amiben megbízunk: a kiterjesztést és a MIME-t a
# böngésző (vagy egy támadó) állítja. A másik kettő azért marad, hogy a
# véletlen félrekattintás érthető hibaüzenetet kapjon, ne rejtélyes elakadást.
CV_FORMATUMOK: dict[str, dict] = {
    "pdf": {
        "kiterjesztesek": (".pdf",),
        "mime": ("application/pdf",),
        "magic": (b"%PDF-",),
        "nev": "PDF",
    },
    "docx": {
        # A .docx valójában ZIP, ezért a magic byte a ZIP-fejléc. Hogy tényleg
        # Word-dokumentum-e, azt a szövegkinyerés dönti el (`python-docx`) --
        # itt csak annyit állítunk, hogy nem valami egészen más fájl.
        "kiterjesztesek": (".docx",),
        "mime": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        "magic": (b"PK\x03\x04",),
        "nev": "DOCX",
    },
    "kep": {
        "kiterjesztesek": (".jpg", ".jpeg", ".png"),
        "mime": ("image/jpeg", "image/png"),
        "magic": (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n"),
        "nev": "JPG vagy PNG",
    },
}

# Néhány rendszer minden csatolmányra ezt küldi MIME-ként. Ettől még a
# kiterjesztés és a magic byte ellenőrzés érvényben marad, tehát nem lyuk:
# az általános MIME önmagában semmit nem enged át.
_ALTALANOS_MIME = {"application/octet-stream", "", None}


def _cv_formatum(filename: str, content_type: str | None) -> str | None:
    """Melyik elfogadott formátumra vall a név és a MIME. None, ha egyikre sem."""

    for kulcs, szabaly in CV_FORMATUMOK.items():
        if not filename.endswith(szabaly["kiterjesztesek"]):
            continue
        if content_type in szabaly["mime"] or content_type in _ALTALANOS_MIME:
            return kulcs
    return None


async def read_validated_cv_file(upload: UploadFile) -> tuple[bytes, str]:
    """Méret-, MIME-, kiterjesztés- és magic-byte ellenőrzött CV-olvasás.

    A `read_validated_pdf` szigorúbb testvére: PDF mellett DOCX-et és képet is
    elfogad, és megmondja, MELYIKET -- a szövegkinyerésnek tudnia kell, mit
    kapott. A méretkorlát ugyanaz, és itt is olvasás közben érvényesül, nem
    utólag: a túl nagy fájl nem kerül be a memóriába egészben.
    """

    settings = get_settings()
    filename = (upload.filename or "").lower()
    formatum = _cv_formatum(filename, upload.content_type)
    if formatum is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feltölthető formátumok: PDF, DOCX, JPG és PNG.",
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
    szabaly = CV_FORMATUMOK[formatum]
    if not content.startswith(szabaly["magic"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"A fájl tartalma nem érvényes {szabaly['nev']}. "
                "Lehet, hogy a kiterjesztése nem egyezik a tényleges típusával."
            ),
        )
    return content, formatum


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
