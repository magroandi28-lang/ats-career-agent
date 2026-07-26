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
    _alap_mockok(monkeypatch, "PROFIL_ELLENORZOTT", intent="allas_kereses")
    app.dependency_overrides[jelenlegi_felhasznalo] = lambda: Felhasznalo()
    try:
        valasz = kliens.post(
            "/api/v1/workflow/action",
            json={"action": "allaskereses_inditasa"},
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
