"""A platform–adat–biztonság alap automatikus tesztjei."""

import asyncio
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import Headers, UploadFile

from backend.main import app
from backend.auth import jelenlegi_felhasznalo
from backend.career_state_machine import CareerAction, CareerIntent
from backend.flow_contract import FlowDecision
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
        "/api/v1/flow/messages",
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


def test_vendeg_uzenet_belepes_nelkul_is_elerheto(monkeypatch):
    """A vendégmódú végpont nem kér bejelentkezést -- ez pont a lényege."""
    from backend import main

    monkeypatch.setattr(main, "flow_vendeg_valasz", lambda _: "Szia! Regisztrálj a részletekért.")

    valasz = kliens.post(
        "/api/v1/flow/guest-messages",
        json={"kerdes": "Mit tud ez az oldal?"},
    )

    assert valasz.status_code == 200
    assert valasz.json() == {"valasz": "Szia! Regisztrálj a részletekért."}


def test_vendeg_uzenet_modell_nelkul_is_alapertelmezett_valaszt_ad(monkeypatch):
    from backend import main

    monkeypatch.setattr(main, "flow_vendeg_valasz", lambda _: "")

    valasz = kliens.post(
        "/api/v1/flow/guest-messages",
        json={"kerdes": "Mit tud ez az oldal?"},
    )

    assert valasz.status_code == 200
    assert valasz.json()["valasz"] == main.VENDEG_ALAPERTELMEZETT_VALASZ


def test_flow_cv_frissites_nem_indit_allaskeresest(monkeypatch):
    """A modell javaslatából csak a cél megerősítése hajtható végre."""
    from backend import main

    class Felhasznalo:
        id = "00000000-0000-0000-0000-000000000001"

    app.dependency_overrides[jelenlegi_felhasznalo] = lambda: Felhasznalo()
    monkeypatch.setattr(main, "session_lekeres_vagy_letrehozas", lambda _: "session-1")
    monkeypatch.setattr(main, "elozmenyek_lekerese", lambda *_: [])
    monkeypatch.setattr(main, "uzenet_mentese", lambda *_, **__: None)
    monkeypatch.setattr(
        main,
        "workflow_lekeres_vagy_letrehozas",
        lambda *_: {
            "id": "workflow-1",
            "current_state": "CEL_TISZTAZATLAN",
            "context": {},
        },
    )
    monkeypatch.setattr(
        main,
        "profile_get_or_create",
        lambda *_: {
            "id": "profile-1",
            "confirmed_data": {},
            "draft_data": {},
            "draft_version": 0,
        },
    )
    frissitesek = []
    monkeypatch.setattr(
        main,
        "workflow_frissites",
        lambda *args: frissitesek.append(args) or True,
    )
    monkeypatch.setattr(main, "gps_esemeny_rogzitese", lambda *_, **__: "event-1")
    monkeypatch.setattr(main, "gps_snapshot_frissites", lambda *_, **__: None)
    monkeypatch.setattr(
        main,
        "flow_dontes",
        lambda *_, **__: FlowDecision(
            intent=CareerIntent.CV_FRISSITES,
            response_message="A CV frissítésével folytatjuk.",
            proposed_action=CareerAction.CEL_MEGEROSITESE,
            confidence=0.99,
        ),
    )

    try:
        valasz = kliens.post(
            "/api/v1/flow/messages",
            json={"kerdes": "Frissítsd a CV-met.", "profil": {}},
        )
    finally:
        app.dependency_overrides.clear()

    assert valasz.status_code == 200
    assert valasz.json()["intent"] == "cv_frissites"
    assert valasz.json()["current_state"] == "CEL_TISZTAZOTT"
    assert valasz.json()["accepted_action"] == "cel_megerositese"
    assert "allaskereses_inditasa" not in valasz.json()["allowed_actions"]
    assert len(frissitesek) == 1


def test_fix_cv_gomb_modell_nelkul_rogziti_az_intentet(monkeypatch):
    from backend import main

    class Felhasznalo:
        id = "00000000-0000-0000-0000-000000000001"

    app.dependency_overrides[jelenlegi_felhasznalo] = lambda: Felhasznalo()
    monkeypatch.setattr(main, "session_lekeres_vagy_letrehozas", lambda _: "session-1")
    monkeypatch.setattr(
        main,
        "workflow_lekeres_vagy_letrehozas",
        lambda *_: {
            "id": "workflow-1",
            "current_state": "CEL_TISZTAZATLAN",
            "context": {},
        },
    )
    frissitesek = []
    monkeypatch.setattr(
        main,
        "workflow_frissites",
        lambda *args: frissitesek.append(args) or True,
    )
    monkeypatch.setattr(
        main,
        "profile_get_or_create",
        lambda *_: {"confirmed_data": {}},
    )
    esemenyek = []
    monkeypatch.setattr(
        main,
        "gps_esemeny_rogzitese",
        lambda *args, **kwargs: esemenyek.append((args, kwargs)) or "event-1",
    )
    monkeypatch.setattr(main, "gps_snapshot_frissites", lambda *_, **__: None)

    try:
        valasz = kliens.post(
            "/api/v1/workflow/intent",
            json={"intent": "cv_frissites"},
        )
    finally:
        app.dependency_overrides.clear()

    assert valasz.status_code == 200
    assert valasz.json()["intent"] == "cv_frissites"
    assert valasz.json()["current_state"] == "PROFIL_HIANYOS"
    assert valasz.json()["readiness"]["missing_fields"] == [
        "cv_document",
        "target_role",
    ]
    assert valasz.json()["model_called"] is False
    assert len(frissitesek) == 1
    assert frissitesek[0][3] is CareerIntent.CV_FRISSITES
    assert esemenyek[0][0][2] == "career_goal_selected"


def test_meglevo_jovahagyott_cv_azonnal_ellenorzott_profilallapot(monkeypatch):
    from backend import main

    class Felhasznalo:
        id = "00000000-0000-0000-0000-000000000001"

    app.dependency_overrides[jelenlegi_felhasznalo] = lambda: Felhasznalo()
    monkeypatch.setattr(main, "session_lekeres_vagy_letrehozas", lambda _: "session-1")
    monkeypatch.setattr(
        main,
        "workflow_lekeres_vagy_letrehozas",
        lambda *_: {
            "id": "workflow-1",
            "current_state": "CV_TERVEZET",
            "context": {},
        },
    )
    monkeypatch.setattr(
        main,
        "profile_get_or_create",
        lambda *_: {
            "confirmed_data": {
                "cv_document_id": "00000000-0000-0000-0000-000000000002",
            },
        },
    )
    updates = []
    monkeypatch.setattr(
        main,
        "workflow_frissites",
        lambda *args: updates.append(args) or True,
    )
    monkeypatch.setattr(main, "gps_esemeny_rogzitese", lambda *_, **__: "event-1")
    monkeypatch.setattr(main, "gps_snapshot_frissites", lambda *_, **__: None)

    try:
        response = kliens.post(
            "/api/v1/workflow/intent",
            json={"intent": "cv_ellenorzes"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["current_state"] == "PROFIL_ELLENORZOTT"
    assert response.json()["readiness"]["ready"] is True
    assert updates[0][2].value == "PROFIL_ELLENORZOTT"


def test_visszalepes_a_szerveroldali_workflowt_is_ujrakezdi(monkeypatch):
    from backend import main

    class Felhasznalo:
        id = "00000000-0000-0000-0000-000000000001"

    app.dependency_overrides[jelenlegi_felhasznalo] = lambda: Felhasznalo()
    monkeypatch.setattr(main, "session_lekeres_vagy_letrehozas", lambda _: "session-1")
    monkeypatch.setattr(
        main,
        "workflow_lekeres_vagy_letrehozas",
        lambda *_: {
            "id": "workflow-1",
            "current_state": "PROFIL_HIANYOS",
        },
    )
    resets = []
    monkeypatch.setattr(
        main,
        "workflow_ujrakezdes",
        lambda *args: resets.append(args) or True,
    )

    try:
        response = kliens.post("/api/v1/workflow/reset")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["current_state"] == "CEL_TISZTAZATLAN"
    assert resets == [
        ("00000000-0000-0000-0000-000000000001", "workflow-1"),
    ]


def test_cv_import_feltoltes_utan_meg_nem_erosit_profilt(monkeypatch):
    from backend import main

    class Felhasznalo:
        id = "00000000-0000-0000-0000-000000000001"

    app.dependency_overrides[jelenlegi_felhasznalo] = lambda: Felhasznalo()

    async def valid_pdf(_):
        return b"%PDF-1.7\nvalid"

    monkeypatch.setattr(main, "read_validated_pdf", valid_pdf)
    monkeypatch.setattr(
        main,
        "cv_import_create",
        lambda *_: {
            "id": "00000000-0000-0000-0000-000000000002",
            "status": "succeeded",
            "file_name": "cv.pdf",
            "storage_path": "user/import.pdf",
            "extracted_text": "Teszt CV szöveg",
            "character_count": 15,
            "review_status": "pending",
        },
    )

    try:
        response = kliens.post(
            "/api/v1/profile/import",
            files={"fajl": ("cv.pdf", b"%PDF-1.7\nvalid", "application/pdf")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["review_status"] == "pending"
    assert response.json()["extracted_text"] == "Teszt CV szöveg"


def test_cv_csak_kulon_review_utan_kerul_a_megerositett_profilba(monkeypatch):
    from backend import main

    class Felhasznalo:
        id = "00000000-0000-0000-0000-000000000001"

    app.dependency_overrides[jelenlegi_felhasznalo] = lambda: Felhasznalo()
    import_id = "00000000-0000-0000-0000-000000000002"
    monkeypatch.setattr(
        main,
        "cv_import_mark_approved",
        lambda *_: {
            "id": import_id,
            "review_status": "approved",
            "extracted_text": "Jóváhagyott CV",
        },
    )
    drafts = []
    monkeypatch.setattr(
        main,
        "profile_update_draft",
        lambda *args: drafts.append(args) or {"draft_version": 1},
    )
    monkeypatch.setattr(
        main,
        "profile_confirm",
        lambda *_: {"id": "snapshot-1", "version": 1},
    )
    monkeypatch.setattr(
        main,
        "profile_get_or_create",
        lambda *_: {"confirmed_data": {"cv_document_id": import_id}},
    )
    monkeypatch.setattr(main, "session_lekeres_vagy_letrehozas", lambda _: "session-1")
    monkeypatch.setattr(
        main,
        "workflow_lekeres_vagy_letrehozas",
        lambda *_: {
            "id": "workflow-1",
            "current_state": "PROFIL_HIANYOS",
            "intent": "cv_ellenorzes",
            "context": {},
        },
    )
    monkeypatch.setattr(main, "workflow_frissites", lambda *_: True)
    monkeypatch.setattr(main, "gps_esemeny_rogzitese", lambda *_, **__: "event-1")
    monkeypatch.setattr(main, "gps_snapshot_frissites", lambda *_, **__: None)

    try:
        response = kliens.post(
            "/api/v1/profile/facts/review",
            json={
                "import_id": import_id,
                "approved_text": "Jóváhagyott CV",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["import"]["review_status"] == "approved"
    assert response.json()["current_state"] == "PROFIL_ELLENORZOTT"
    assert drafts[0][1] == {"cv_document_id": import_id}


def test_megerositett_minimumprofil_atlep_ellenorzott_allapotba(monkeypatch):
    from backend import main

    class Felhasznalo:
        id = "00000000-0000-0000-0000-000000000001"

    app.dependency_overrides[jelenlegi_felhasznalo] = lambda: Felhasznalo()
    monkeypatch.setattr(main, "session_lekeres_vagy_letrehozas", lambda _: "session-1")
    monkeypatch.setattr(
        main,
        "profile_confirm",
        lambda *_: {"id": "snapshot-1", "version": 1},
    )
    monkeypatch.setattr(
        main,
        "profile_get_or_create",
        lambda *_: {
            "id": "profile-1",
            "confirmed_data": {
                "target_role": "automata tesztelő",
                "skills": ["Python", "Playwright"],
                "location": "Budapest",
            },
        },
    )
    monkeypatch.setattr(
        main,
        "workflow_lekeres_vagy_letrehozas",
        lambda *_: {
            "id": "workflow-1",
            "current_state": "CEL_TISZTAZOTT",
            "intent": "allas_kereses",
            "context": {},
        },
    )
    updates = []
    monkeypatch.setattr(
        main,
        "workflow_frissites",
        lambda *args: updates.append(args) or True,
    )
    monkeypatch.setattr(main, "gps_esemeny_rogzitese", lambda *_, **__: "event-1")
    monkeypatch.setattr(main, "gps_snapshot_frissites", lambda *_, **__: None)

    try:
        response = kliens.post(
            "/api/v1/profile/confirm",
            json={
                "fields": ["target_role", "skills", "location"],
                "reason": "user_confirmation",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["readiness"]["ready"] is True
    assert response.json()["current_state"] == "PROFIL_ELLENORZOTT"
    assert response.json()["state_changed"] is True
    assert len(updates) == 1
