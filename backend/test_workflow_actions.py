"""A folyamat-műveletek kapujának, végrehajtásának és GPS-nyomának tesztjei."""

import pytest
from fastapi.testclient import TestClient

from backend.auth import jelenlegi_felhasznalo
from backend.career_state_machine import CareerAction
from backend.gps_vocabulary import (
    GpsSzokincsHiba,
    ellenorzott_esemeny,
    ellenorzott_snapshot,
)
from backend.main import app
from backend.security import rate_limiter
from backend.workflow_actions import (
    ActionContext,
    ActionError,
    ActionOutcome,
    GpsNyomHiba,
    execute_action,
)

kliens = TestClient(app)

FELHASZNALO_ID = "00000000-0000-0000-0000-000000000001"


class Felhasznalo:
    id = FELHASZNALO_ID


@pytest.fixture(autouse=True)
def limiter_urites():
    rate_limiter.clear()
    yield
    rate_limiter.clear()


# ── A zárt szókincs őrzése ────────────────────────────────────────────

def test_ismeretlen_esemenytipus_hangosan_bukik():
    """Korábban az ilyen érték csak az adatbázisban, némán hasalt el."""
    with pytest.raises(GpsSzokincsHiba):
        ellenorzott_esemeny("profile_snapshot_activated")


def test_ervenyes_esemenytipus_atmegy():
    assert ellenorzott_esemeny("market_snapshot_ready") == "market_snapshot_ready"


def test_terulethez_nem_illo_allapot_elutasitva():
    """A `betoltve` a piaci képre igaz, a profilra nem."""
    assert ellenorzott_snapshot("piaci_kep", "betoltve") == ("piaci_kep", "betoltve")
    with pytest.raises(GpsSzokincsHiba):
        ellenorzott_snapshot("profil", "betoltve")


def test_ismeretlen_terulet_elutasitva():
    with pytest.raises(GpsSzokincsHiba):
        ellenorzott_snapshot("nincs_ilyen", "megerositett")


def test_action_outcome_ellenorzi_a_gps_nyomot():
    with pytest.raises(GpsSzokincsHiba):
        ActionOutcome(
            result={},
            gps_esemeny="market_snapshot_ready",
            gps_terulet="piaci_kep",
            gps_allapot="megerositett",
        )


def test_felig_megadott_gps_nyom_programozoi_hiba():
    with pytest.raises(GpsNyomHiba):
        ActionOutcome(result={}, gps_terulet="piaci_kep")


# ── Piaci körkép művelet ──────────────────────────────────────────────

def test_piaci_korkep_celmunkakor_nelkul_elutasit():
    """Megerősített cél nélkül nincs mihez viszonyítani."""
    with pytest.raises(ActionError):
        execute_action(
            CareerAction.PIACI_KORKEP_INDITASA,
            ActionContext(
                user_id=FELHASZNALO_ID,
                workflow={"context": {}},
                profile={"confirmed_data": {}},
            ),
        )


def test_piaci_korkep_vazlatbol_nem_dolgozik(monkeypatch):
    """A vázlat még nem tény: a draft célmunkakör nem elég."""
    with pytest.raises(ActionError):
        execute_action(
            CareerAction.PIACI_KORKEP_INDITASA,
            ActionContext(
                user_id=FELHASZNALO_ID,
                workflow={"context": {}},
                profile={
                    "draft_data": {"target_role": "automata tesztelő"},
                    "confirmed_data": {},
                },
            ),
        )


def test_piaci_korkep_adat_nelkul_ertheto_hibat_ad(monkeypatch):
    from backend import workflow_actions

    monkeypatch.setattr(workflow_actions, "szakma_statisztika", lambda _: {})
    monkeypatch.setattr(workflow_actions, "kereslet_korkep", lambda: [])
    monkeypatch.setattr(workflow_actions, "ksh_kereset", lambda _: None)

    with pytest.raises(ActionError, match="nincs elég saját piaci adatunk"):
        execute_action(
            CareerAction.PIACI_KORKEP_INDITASA,
            ActionContext(
                user_id=FELHASZNALO_ID,
                workflow={"context": {}},
                profile={"confirmed_data": {"target_role": "automata tesztelő"}},
            ),
        )


def test_piaci_korkep_mert_adatot_ad_vissza(monkeypatch):
    from backend import workflow_actions

    monkeypatch.setattr(
        workflow_actions,
        "szakma_statisztika",
        lambda _: {
            "hirdetesek_szama": 42,
            "keszsegek": [{"keszseg": "Python", "hirdetesek_szazaleka": 61}],
            "bersavok": ["600-800 eFt"],
        },
    )
    monkeypatch.setattr(
        workflow_actions,
        "kereslet_korkep",
        lambda: [
            {"szakma": "Automata tesztelő", "friss_30": 42, "kategoria": "📈 növekvő"},
            {"szakma": "Bolti eladó", "friss_30": 7, "kategoria": "➡️ stabil"},
        ],
    )
    monkeypatch.setattr(workflow_actions, "ksh_kereset", lambda _: None)

    outcome = execute_action(
        CareerAction.PIACI_KORKEP_INDITASA,
        ActionContext(
            user_id=FELHASZNALO_ID,
            workflow={"context": {}},
            profile={"confirmed_data": {"target_role": "automata tesztelő"}},
        ),
    )

    # A szakmanév egyeztetése kis-nagybetűtől független.
    assert outcome.result["kereslet"]["friss_30"] == 42
    assert outcome.result["hirdetesek_szama"] == 42
    assert outcome.gps_esemeny == "market_snapshot_ready"
    assert outcome.gps_terulet == "piaci_kep"
    assert outcome.gps_allapot == "betoltve"
    assert outcome.context_patch == {"piaci_kep_szakma": "automata tesztelő"}


# ── Álláskeresés ──────────────────────────────────────────────────────

def _profil(**megerositett) -> dict:
    return {"confirmed_data": megerositett}


TELJES_KERESO_PROFIL = {
    "target_role": "automata tesztelő",
    "skills": ["Python", "Playwright"],
    "location": "Budapest",
}


def test_allaskereses_helyszin_nelkul_elutasit():
    with pytest.raises(ActionError, match="hol keresel munkát"):
        execute_action(
            CareerAction.ALLASKERESES_INDITASA,
            ActionContext(
                user_id=FELHASZNALO_ID,
                workflow={"context": {}},
                profile=_profil(target_role="automata tesztelő", skills=["Python"]),
            ),
        )


def test_allaskereses_keszseg_nelkul_elutasit():
    with pytest.raises(ActionError, match="készségedet"):
        execute_action(
            CareerAction.ALLASKERESES_INDITASA,
            ActionContext(
                user_id=FELHASZNALO_ID,
                workflow={"context": {}},
                profile=_profil(target_role="automata tesztelő", location="Budapest"),
            ),
        )


def test_allaskereses_inditasa_meg_nem_ad_talalatot():
    """A keresés indítása és az eredmény két külön lépés."""
    outcome = execute_action(
        CareerAction.ALLASKERESES_INDITASA,
        ActionContext(
            user_id=FELHASZNALO_ID,
            workflow={"context": {}},
            profile=_profil(**TELJES_KERESO_PROFIL),
        ),
    )

    assert outcome.result["talalat_meg_nincs"] is True
    assert "allasok" not in outcome.result
    assert outcome.gps_terulet == "palyazas"
    assert outcome.gps_allapot == "nincs_shortlist"
    assert outcome.gps_esemeny is None


def test_allasok_bemutatasa_legfeljebb_otot_ad(monkeypatch):
    from backend import workflow_actions

    hivasok = []
    monkeypatch.setattr(
        workflow_actions,
        "allasok_minosegi_kereses",
        lambda cv, info, hely: hivasok.append((cv, info, hely))
        or {
            "allasok": [{"cim": f"Allas {i}"} for i in range(9)],
            "forras": "adatbazis",
        },
    )
    monkeypatch.setattr(
        workflow_actions, "_shortlist_mentese", lambda *_: "shortlist-1"
    )
    monkeypatch.setattr(workflow_actions, "cv_import_get", lambda *_: None)

    outcome = execute_action(
        CareerAction.ALLASOK_BEMUTATASA,
        ActionContext(
            user_id=FELHASZNALO_ID,
            workflow={"context": {}},
            profile=_profil(**TELJES_KERESO_PROFIL),
        ),
    )

    assert outcome.result["talalatok_szama"] == 5
    assert outcome.gps_esemeny == "job_shortlist_created"
    assert outcome.gps_allapot == "shortlist"
    assert outcome.context_patch == {"shortlist_id": "shortlist-1"}

    # A szakma_info a megerősített profilból épül, nem modellhívásból.
    _, szakma_info, helyszin = hivasok[0]
    assert szakma_info["szakma"] == "automata tesztelő"
    assert szakma_info["utos_kulcsszavak"] == ["Python", "Playwright"]
    assert helyszin == "Budapest"


def test_nulla_talalat_eseten_nincs_shortlist_allapot(monkeypatch):
    from backend import workflow_actions

    monkeypatch.setattr(
        workflow_actions,
        "allasok_minosegi_kereses",
        lambda *_: {"allasok": [], "piaci_jelzes": "csökkenő kereslet"},
    )
    monkeypatch.setattr(workflow_actions, "_shortlist_mentese", lambda *_: None)
    monkeypatch.setattr(workflow_actions, "cv_import_get", lambda *_: None)

    outcome = execute_action(
        CareerAction.ALLASOK_BEMUTATASA,
        ActionContext(
            user_id=FELHASZNALO_ID,
            workflow={"context": {}},
            profile=_profil(**TELJES_KERESO_PROFIL),
        ),
    )

    assert outcome.result["talalatok_szama"] == 0
    assert outcome.gps_allapot == "nincs_shortlist"
    assert outcome.result["piaci_jelzes"] == "csökkenő kereslet"


def test_jova_nem_hagyott_cv_nem_kerul_a_kereresbe(monkeypatch):
    """Feltöltés önmagában nem tény: csak átnézett szöveget használunk."""
    from backend import workflow_actions

    hivasok = []
    monkeypatch.setattr(
        workflow_actions,
        "allasok_minosegi_kereses",
        lambda cv, info, hely: hivasok.append(cv) or {"allasok": []},
    )
    monkeypatch.setattr(workflow_actions, "_shortlist_mentese", lambda *_: None)
    monkeypatch.setattr(
        workflow_actions,
        "cv_import_get",
        lambda *_: {"review_status": "pending", "extracted_text": "NYERS CV"},
    )

    execute_action(
        CareerAction.ALLASOK_BEMUTATASA,
        ActionContext(
            user_id=FELHASZNALO_ID,
            workflow={"context": {}},
            profile=_profil(
                **TELJES_KERESO_PROFIL,
                cv_document_id="00000000-0000-0000-0000-000000000002",
            ),
        ),
    )

    assert hivasok == [""]


# ── CV-átvizsgálás (konkrét álláshirdetés nélkül) ─────────────────────

def _rendes_cv(extra: str = "") -> str:
    return (
        "Kiss Péter szobafestő\n"
        "kiss.peter@example.hu\n"
        "+36 30 123 4567\n"
        + "\n".join(
            ["Tapasztalat: falfestés, glettelés, tapétázás, felújítás."] * 20
        )
        + extra
    )


def test_formai_vizsgalat_tiszta_cv_nel_nem_kifogasol():
    from backend.workflow_actions import _formai_kifogasok

    assert _formai_kifogasok(_rendes_cv()) == []


def test_formai_vizsgalat_eszreveszi_a_hianyzo_elerhetoseget():
    from backend.workflow_actions import _formai_kifogasok

    kodok = {k["kod"] for k in _formai_kifogasok("Szobafestő vagyok. " * 60)}
    assert "nincs_email" in kodok
    assert "nincs_telefon" in kodok


def test_formai_vizsgalat_jelzi_a_kepkent_beolvasott_cv_t():
    """Szkennelt CV-nél alig van kinyerhető szöveg."""
    from backend.workflow_actions import _formai_kifogasok

    kodok = {k["kod"] for k in _formai_kifogasok("Kiss Péter\nszobafestő")}
    assert "keves_szoveg" in kodok


def test_formai_vizsgalat_jelzi_az_osszefolyo_sorokat():
    from backend.workflow_actions import _formai_kifogasok

    # Két hasábos PDF-ből kinyerve a sorok jelentős része összefolyik.
    hosszu = ["Tapasztalat és képzettség egy sorba olvadva. " * 10] * 8
    szoveg = "\n".join([_rendes_cv()] + hosszu)
    kodok = {k["kod"] for k in _formai_kifogasok(szoveg)}
    assert "osszefolyo_sorok" in kodok


def test_cv_ellenorzes_jovahagyott_cv_nelkul_elutasit(monkeypatch):
    from backend import workflow_actions

    monkeypatch.setattr(workflow_actions, "cv_import_get", lambda *_: None)
    with pytest.raises(ActionError, match="töltsd fel"):
        execute_action(
            CareerAction.CV_ELLENORZES_INDITASA,
            ActionContext(
                user_id=FELHASZNALO_ID,
                workflow={"context": {}},
                profile=_profil(target_role="szobafestő"),
            ),
        )


def test_cv_ellenorzes_hirdetes_nelkul_is_ad_hianylistat(monkeypatch):
    """A szakma piaci elvárásaihoz mér, nem konkrét álláshirdetéshez."""
    from backend import workflow_actions

    monkeypatch.setattr(
        workflow_actions,
        "cv_import_get",
        lambda *_: {"review_status": "approved", "extracted_text": _rendes_cv()},
    )
    monkeypatch.setattr(
        workflow_actions,
        "ats_diagnozis_determinisztikus",
        lambda cv, info: {
            "illeszkedes_szazalek": 62,
            "hianyzo_kulcsszavak": [{"szo": "HACCP"}, {"szo": "állványozás"}],
            "meglevo_kulcsszavak": ["glettelés"],
            "fo_problema": "Hiányzik két gyakori elvárás.",
        },
    )

    outcome = execute_action(
        CareerAction.CV_ELLENORZES_INDITASA,
        ActionContext(
            user_id=FELHASZNALO_ID,
            workflow={"context": {}},
            profile=_profil(
                target_role="szobafestő",
                cv_document_id="00000000-0000-0000-0000-000000000002",
            ),
        ),
    )

    assert outcome.result["illeszkedes_szazalek"] == 62
    assert len(outcome.result["hianyzo_elvarasok"]) == 2
    assert outcome.result["formai_kifogasok"] == []
    assert outcome.gps_terulet == "felkeszultseg"
    assert outcome.gps_allapot == "hianyok"


# ── Flow mint orchestrator ────────────────────────────────────────────

def _flow_mockok(monkeypatch, allapot, javasolt_akcio, intent="piaci_korkep"):
    """A Flow-üzenet végpont körüli szerveroldali réteg kiváltása."""
    from backend import main
    from backend.career_state_machine import CareerIntent
    from backend.flow_contract import FlowDecision

    monkeypatch.setattr(main, "session_lekeres_vagy_letrehozas", lambda _: "session-1")
    monkeypatch.setattr(main, "elozmenyek_lekerese", lambda *_: [])
    monkeypatch.setattr(main, "uzenet_mentese", lambda *_, **__: None)
    monkeypatch.setattr(main, "gps_projekcio", lambda *_: [])
    monkeypatch.setattr(
        main,
        "workflow_lekeres_vagy_letrehozas",
        lambda *_: {
            "id": "workflow-1",
            "current_state": allapot,
            "intent": intent,
            "context": {},
        },
    )
    monkeypatch.setattr(
        main,
        "profile_get_or_create",
        lambda *_: {"confirmed_data": {"target_role": "automata tesztelő"}},
    )
    monkeypatch.setattr(main, "gps_esemeny_rogzitese", lambda *_, **__: "event-1")
    monkeypatch.setattr(main, "gps_snapshot_frissites", lambda *_, **__: None)
    monkeypatch.setattr(
        main,
        "flow_dontes",
        lambda *_, **__: FlowDecision(
            intent=CareerIntent.PIACI_KORKEP,
            response_message="Megnézem a piaci helyzetet.",
            proposed_action=javasolt_akcio,
            confidence=0.95,
        ),
    )
    return main


def test_flow_javaslata_le_is_fut(monkeypatch):
    """Elég annyit mondani Flow-nak, hogy csinálja -- nem kell gombot keresni."""
    main = _flow_mockok(
        monkeypatch, "PROFIL_ELLENORZOTT", CareerAction.PIACI_KORKEP_INDITASA
    )
    from backend import workflow_actions

    monkeypatch.setattr(
        workflow_actions,
        "szakma_statisztika",
        lambda _: {"hirdetesek_szama": 41, "keszsegek": [], "bersavok": []},
    )
    monkeypatch.setattr(workflow_actions, "kereslet_korkep", lambda: [])
    monkeypatch.setattr(workflow_actions, "ksh_kereset", lambda _: None)
    frissitesek = []
    monkeypatch.setattr(
        main, "workflow_frissites", lambda *args: frissitesek.append(args) or True
    )

    app.dependency_overrides[jelenlegi_felhasznalo] = lambda: Felhasznalo()
    try:
        valasz = kliens.post(
            "/api/v1/flow/messages", json={"kerdes": "Nézzük a piacot."}
        )
    finally:
        app.dependency_overrides.clear()

    test = valasz.json()
    assert valasz.status_code == 200
    assert test["accepted_action"] == "piaci_korkep_inditasa"
    assert test["current_state"] == "PIACI_KEP_KESZ"
    assert test["eredmeny"]["hirdetesek_szama"] == 41
    assert len(frissitesek) == 1


def test_flow_tiltott_javaslata_nem_fut_le(monkeypatch):
    """A chat ugyanazon a kapun megy át, mint a gombok: ATS hirdetés nélkül nem indul."""
    main = _flow_mockok(
        monkeypatch, "PROFIL_ELLENORZOTT", CareerAction.ATS_ELEMZES_INDITASA
    )
    frissitesek = []
    monkeypatch.setattr(
        main, "workflow_frissites", lambda *args: frissitesek.append(args) or True
    )

    app.dependency_overrides[jelenlegi_felhasznalo] = lambda: Felhasznalo()
    try:
        valasz = kliens.post(
            "/api/v1/flow/messages", json={"kerdes": "Csinálj ATS-t."}
        )
    finally:
        app.dependency_overrides.clear()

    test = valasz.json()
    assert valasz.status_code == 200
    assert test["accepted_action"] is None
    assert test["current_state"] == "PROFIL_ELLENORZOTT"
    assert test["eredmeny"] is None
    assert frissitesek == []


def test_elhasalt_modul_utan_a_beszelgetes_megy_tovabb(monkeypatch):
    """Flow már megszólalt: a hibától ne álljon meg a chat, de az állapot se változzon."""
    main = _flow_mockok(
        monkeypatch, "PROFIL_ELLENORZOTT", CareerAction.PIACI_KORKEP_INDITASA
    )
    monkeypatch.setattr(
        main,
        "profile_get_or_create",
        lambda *_: {"confirmed_data": {}},  # nincs megerősített célmunkakör
    )
    frissitesek = []
    monkeypatch.setattr(
        main, "workflow_frissites", lambda *args: frissitesek.append(args) or True
    )

    app.dependency_overrides[jelenlegi_felhasznalo] = lambda: Felhasznalo()
    try:
        valasz = kliens.post(
            "/api/v1/flow/messages", json={"kerdes": "Nézzük a piacot."}
        )
    finally:
        app.dependency_overrides.clear()

    test = valasz.json()
    assert valasz.status_code == 200
    assert test["response_message"] == "Megnézem a piaci helyzetet."
    assert "célmunkakörödet" in test["muvelet_hiba"]
    assert test["current_state"] == "PROFIL_ELLENORZOTT"
    assert frissitesek == []


# ── A végpont kapuja ──────────────────────────────────────────────────

def _alap_mockok(monkeypatch, allapot, intent="piaci_korkep", context=None):
    from backend import main

    monkeypatch.setattr(main, "session_lekeres_vagy_letrehozas", lambda _: "session-1")
    monkeypatch.setattr(
        main,
        "workflow_lekeres_vagy_letrehozas",
        lambda *_: {
            "id": "workflow-1",
            "current_state": allapot,
            "intent": intent,
            "context": context or {},
        },
    )
    monkeypatch.setattr(
        main,
        "profile_get_or_create",
        lambda *_: {"confirmed_data": {"target_role": "automata tesztelő"}},
    )
    return main


def test_nem_engedelyezett_lepes_409(monkeypatch):
    _alap_mockok(monkeypatch, "CEL_TISZTAZATLAN")
    app.dependency_overrides[jelenlegi_felhasznalo] = lambda: Felhasznalo()
    try:
        valasz = kliens.post(
            "/api/v1/workflow/action",
            json={"action": "piaci_korkep_inditasa"},
        )
    finally:
        app.dependency_overrides.clear()

    assert valasz.status_code == 409


def test_cel_nelkul_nem_indithato_muvelet(monkeypatch):
    _alap_mockok(monkeypatch, "PROFIL_ELLENORZOTT", intent=None)
    app.dependency_overrides[jelenlegi_felhasznalo] = lambda: Felhasznalo()
    try:
        valasz = kliens.post(
            "/api/v1/workflow/action",
            json={"action": "piaci_korkep_inditasa"},
        )
    finally:
        app.dependency_overrides.clear()

    assert valasz.status_code == 409


def test_meg_be_nem_kotott_lepes_501(monkeypatch):
    """Az állapotgép ismeri az átmenetet, de a modul még nem készült el.

    Ez szándékosan más, mint a 409: ott a lépés tiltott, itt még hiányzik.
    """
    _alap_mockok(monkeypatch, "PROFIL_ELLENORZOTT", intent="tanacsadas")
    app.dependency_overrides[jelenlegi_felhasznalo] = lambda: Felhasznalo()
    try:
        valasz = kliens.post(
            "/api/v1/workflow/action",
            json={"action": "tanacsadas_inditasa"},
        )
    finally:
        app.dependency_overrides.clear()

    assert valasz.status_code == 501


def test_sikeres_muvelet_lepteti_az_allapotot_es_gps_nyomot_hagy(monkeypatch):
    main = _alap_mockok(monkeypatch, "PROFIL_ELLENORZOTT")
    from backend import workflow_actions

    monkeypatch.setattr(
        workflow_actions,
        "szakma_statisztika",
        lambda _: {"hirdetesek_szama": 42, "keszsegek": [], "bersavok": []},
    )
    monkeypatch.setattr(workflow_actions, "kereslet_korkep", lambda: [])
    monkeypatch.setattr(workflow_actions, "ksh_kereset", lambda _: None)

    frissitesek = []
    monkeypatch.setattr(
        main, "workflow_frissites", lambda *args: frissitesek.append(args) or True
    )
    esemenyek = []
    monkeypatch.setattr(
        main,
        "gps_esemeny_rogzitese",
        lambda *args, **kwargs: esemenyek.append(args) or "event-1",
    )
    snapshotok = []
    monkeypatch.setattr(
        main,
        "gps_snapshot_frissites",
        lambda *args: snapshotok.append(args) or None,
    )

    app.dependency_overrides[jelenlegi_felhasznalo] = lambda: Felhasznalo()
    try:
        valasz = kliens.post(
            "/api/v1/workflow/action",
            json={"action": "piaci_korkep_inditasa"},
        )
    finally:
        app.dependency_overrides.clear()

    assert valasz.status_code == 200
    test = valasz.json()
    assert test["previous_state"] == "PROFIL_ELLENORZOTT"
    assert test["current_state"] == "PIACI_KEP_KESZ"
    assert test["state_changed"] is True
    assert test["result"]["hirdetesek_szama"] == 42

    # Az állapot csak a modul sikeres lefutása után mentődik.
    assert len(frissitesek) == 1
    assert frissitesek[0][2].value == "PIACI_KEP_KESZ"
    assert frissitesek[0][4]["piaci_kep_szakma"] == "automata tesztelő"
    assert esemenyek[0][2] == "market_snapshot_ready"
    assert snapshotok[0][1:3] == ("piaci_kep", "betoltve")


def test_elhasalt_modul_nem_lepteti_az_allapotot(monkeypatch):
    """Hibás modul nem hagyhat félkész folyamatot maga után."""
    main = _alap_mockok(monkeypatch, "PROFIL_ELLENORZOTT")
    from backend import workflow_actions

    monkeypatch.setattr(workflow_actions, "szakma_statisztika", lambda _: {})
    monkeypatch.setattr(workflow_actions, "kereslet_korkep", lambda: [])
    monkeypatch.setattr(workflow_actions, "ksh_kereset", lambda _: None)

    frissitesek = []
    monkeypatch.setattr(
        main, "workflow_frissites", lambda *args: frissitesek.append(args) or True
    )

    app.dependency_overrides[jelenlegi_felhasznalo] = lambda: Felhasznalo()
    try:
        valasz = kliens.post(
            "/api/v1/workflow/action",
            json={"action": "piaci_korkep_inditasa"},
        )
    finally:
        app.dependency_overrides.clear()

    assert valasz.status_code == 422
    assert frissitesek == []
