"""A platform–adat–biztonság alap automatikus tesztjei."""

import asyncio
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import Headers, UploadFile

from backend.main import app
from backend.security import (
    FixedWindowRateLimiter,
    read_validated_pdf,
    rate_limiter,
)
from backend.settings import get_settings

kliens = TestClient(app)


@pytest.fixture(autouse=True)
def limiter_urites():
    rate_limiter.clear()
    yield
    rate_limiter.clear()


def test_healthz_valaszol():
    valasz = kliens.get("/healthz")

    assert valasz.status_code == 200
    assert valasz.json() == {"status": "ok", "uzenet": "Elek!"}


def test_live_health_kulso_kapcsolat_nelkul_is_valaszol():
    valasz = kliens.get("/health/live")

    assert valasz.status_code == 200
    assert valasz.json() == {"status": "ok"}


def test_uzleti_vegpont_bejelentkezes_nelkul_nem_elerheto():
    valasz = kliens.get("/piaci-korkep")

    assert valasz.status_code == 401
    assert valasz.headers["www-authenticate"] == "Bearer"


def test_biztonsagi_fejlecek_es_request_id_megjelennek():
    valasz = kliens.get("/health/live", headers={"X-Request-ID": "teszt-azonosito-123"})

    assert valasz.headers["x-request-id"] == "teszt-azonosito-123"
    assert valasz.headers["x-content-type-options"] == "nosniff"
    assert valasz.headers["x-frame-options"] == "DENY"
    assert valasz.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_tul_nagy_deklaralt_keres_blokkolva():
    valasz = kliens.post(
        "/flow-chat",
        content=b"",
        headers={"Content-Length": str(3 * 1024 * 1024)},
    )

    assert valasz.status_code == 413


def test_nem_pdf_tartalom_blokkolva():
    upload = UploadFile(
        BytesIO(b"ez nem pdf"),
        filename="cv.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )

    with pytest.raises(Exception) as hiba:
        asyncio.run(read_validated_pdf(upload))

    assert getattr(hiba.value, "status_code", None) == 400


def test_valodi_pdf_fejlec_elfogadva():
    tartalom = b"%PDF-1.7\nminimalis teszt"
    upload = UploadFile(
        BytesIO(tartalom),
        filename="cv.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )

    assert asyncio.run(read_validated_pdf(upload)) == tartalom


def test_rate_limiter_kiszamithatoan_blokkol():
    limiter = FixedWindowRateLimiter()

    limiter.check("azonos-kulcs", limit=2)
    limiter.check("azonos-kulcs", limit=2)
    with pytest.raises(Exception) as hiba:
        limiter.check("azonos-kulcs", limit=2)

    assert getattr(hiba.value, "status_code", None) == 429


def test_uj_kulcsnevek_elonyben_reszesulnek(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://pelda.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_uj")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "regi-anon")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_uj")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "regi-service")
    get_settings.cache_clear()

    beallitas = get_settings()

    assert beallitas.supabase_publishable_key == "sb_publishable_uj"
    assert beallitas.supabase_secret_key == "sb_secret_uj"
    get_settings.cache_clear()
