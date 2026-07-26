"""A karrierfolyamat determinisztikus szabályainak tesztjei."""

import pytest

from backend.career_state_machine import (
    SPECIFIKACIORA_VARO_AKCIOK,
    TERMINAL_STATE,
    CareerAction,
    CareerIntent,
    CareerState,
    GlobalAction,
    allowed_actions,
    confirm_intent_transition,
    global_next_state,
    next_state,
    reachable_states,
    start_action_for_intent,
)


def test_cv_ellenorzes_nem_indit_allaskeresest():
    assert start_action_for_intent(CareerIntent.CV_ELLENORZES) == (
        CareerAction.CV_ELLENORZES_INDITASA
    )
    assert start_action_for_intent(CareerIntent.CV_ELLENORZES) != (
        CareerAction.ALLASKERESES_INDITASA
    )


def test_bizonytalan_szandek_nem_erositheto_meg():
    assert confirm_intent_transition(
        CareerState.CEL_TISZTAZATLAN,
        CareerIntent.BIZONYTALAN,
    ) is None


def test_egyertelmu_szandek_eloszor_csak_a_celt_rogziti():
    assert confirm_intent_transition(
        CareerState.CEL_TISZTAZATLAN,
        CareerIntent.ALLAS_KERESES,
    ) == CareerState.CEL_TISZTAZOTT


def test_ats_nem_indithato_profil_elott():
    assert next_state(
        CareerState.CEL_TISZTAZOTT,
        CareerAction.PALYAZAS_INDITASA,
    ) is None


def test_engedelyezett_akciok_allapotfuggok():
    assert allowed_actions(CareerState.CEL_TISZTAZATLAN) == (
        CareerAction.CEL_MEGEROSITESE,
        CareerAction.TISZTAZO_KERDES,
    )
    assert CareerAction.ALLASKERESES_INDITASA in allowed_actions(
        CareerState.PROFIL_ELLENORZOTT
    )


# ── A kanonikus pályázási út (felhasznaloi-allapotgep.md 5.) ──────────

KANONIKUS_UT = (
    (CareerState.CEL_TISZTAZATLAN, CareerAction.CEL_MEGEROSITESE,
     CareerState.CEL_TISZTAZOTT),
    (CareerState.CEL_TISZTAZOTT, CareerAction.PROFIL_ADATOK_BEKERESE,
     CareerState.PROFIL_HIANYOS),
    (CareerState.PROFIL_HIANYOS, CareerAction.PROFIL_MEGEROSITESE,
     CareerState.PROFIL_ELLENORZOTT),
    (CareerState.PROFIL_ELLENORZOTT, CareerAction.ALLASKERESES_INDITASA,
     CareerState.ALLASKERESES_AKTIV),
    (CareerState.ALLASKERESES_AKTIV, CareerAction.ALLASOK_BEMUTATASA,
     CareerState.ALLASOK_BEMUTATVA),
    (CareerState.ALLASOK_BEMUTATVA, CareerAction.ALLAS_KIVALASZTASA,
     CareerState.ALLAS_KIVALASZTVA),
    (CareerState.ALLAS_KIVALASZTVA, CareerAction.PALYAZAS_INDITASA,
     CareerState.HIRDETES_ELLENORZOTT),
    (CareerState.HIRDETES_ELLENORZOTT, CareerAction.ATS_ELEMZES_INDITASA,
     CareerState.ATS_KESZ),
    (CareerState.ATS_KESZ, CareerAction.PALYAZATI_CSOMAG_KESZITESE,
     CareerState.PALYAZATI_CSOMAG_TERVEZET),
    (CareerState.PALYAZATI_CSOMAG_TERVEZET, CareerAction.CSOMAG_JOVAHAGYASA,
     CareerState.KULDESRE_JOVAHAGYVA),
    (CareerState.KULDESRE_JOVAHAGYVA, CareerAction.KULSO_MUVELET_INDITASA,
     CareerState.PALYAZAS_ELINDITVA),
    (CareerState.PALYAZAS_ELINDITVA, CareerAction.BEADAS_IGAZOLASA,
     CareerState.PALYAZAS_BEADVA_NAPLOZVA),
)


@pytest.mark.parametrize("allapot,akcio,vart", KANONIKUS_UT)
def test_kanonikus_ut_minden_lepese_atjarhato(allapot, akcio, vart):
    assert next_state(allapot, akcio) is vart


def test_a_teljes_ut_vegigjarhato_a_beadasig():
    allapot = CareerState.CEL_TISZTAZATLAN
    for _, akcio, _ in KANONIKUS_UT:
        kovetkezo = next_state(allapot, akcio)
        assert kovetkezo is not None, f"{allapot} + {akcio} nem vezet sehova"
        allapot = kovetkezo
    assert allapot is TERMINAL_STATE


def test_minden_deklaralt_allapotba_vezet_ut():
    """Nem maradhat olyan állapot, amit a gráf sosem ér el."""
    elerhetetlen = set(CareerState) - reachable_states()
    assert not elerhetetlen, f"Elérhetetlen állapotok: {sorted(elerhetetlen)}"


# ── Elfogadási feltételek (felhasznaloi-allapotgep.md 12.) ────────────

def test_ats_nem_futhat_ellenorzott_hirdetes_nelkul():
    """4. elfogadási feltétel."""
    for allapot in (
        CareerState.PROFIL_ELLENORZOTT,
        CareerState.ALLASOK_BEMUTATVA,
        CareerState.ALLAS_KIVALASZTVA,
    ):
        assert next_state(allapot, CareerAction.ATS_ELEMZES_INDITASA) is None


def test_kulso_kuldes_csak_jovahagyott_csomagbol_indul():
    """6. elfogadási feltétel: jóváhagyás nélkül nincs külső művelet."""
    for allapot in (
        CareerState.ATS_KESZ,
        CareerState.PALYAZATI_CSOMAG_TERVEZET,
    ):
        assert next_state(allapot, CareerAction.KULSO_MUVELET_INDITASA) is None
    assert next_state(
        CareerState.KULDESRE_JOVAHAGYVA,
        CareerAction.KULSO_MUVELET_INDITASA,
    ) is CareerState.PALYAZAS_ELINDITVA


def test_allaskereses_nem_ugorhat_egybol_talalatra():
    """3. elfogadási feltétel: a keresés indítása még nem eredmény."""
    assert next_state(
        CareerState.PROFIL_ELLENORZOTT,
        CareerAction.ALLASOK_BEMUTATASA,
    ) is None


def test_cv_tervezetbol_csak_jovahagyassal_lesz_verzio():
    assert next_state(
        CareerState.CV_TERVEZET,
        CareerAction.CV_JOVAHAGYASA,
    ) is CareerState.CV_JOVAHAGYOTT
    assert next_state(
        CareerState.CV_TERVEZET,
        CareerAction.ALLASKERESES_INDITASA,
    ) is None


def test_a_beadas_utan_nincs_tovabbi_atmenet():
    """A kanonikus folyamat határa a beadás naplózása."""
    assert allowed_actions(TERMINAL_STATE) == ()


# ── Bármely állapotból elérhető visszalépések (5. szakasz) ────────────

@pytest.mark.parametrize("akcio,vart", [
    (GlobalAction.CEL_MODOSITASA, CareerState.CEL_TISZTAZOTT),
    (GlobalAction.PROFIL_VALTOZOTT, CareerState.PROFIL_HIANYOS),
    (GlobalAction.FELADAT_MEGSZAKITASA, CareerState.CEL_TISZTAZATLAN),
])
def test_globalis_visszalepes_minden_akciohoz_celallapotot_ad(akcio, vart):
    assert global_next_state(akcio) is vart


def test_kepzes_es_portfolio_meg_specifikaciora_var():
    """Dokumentált hiány: a terv nem nevez meg hozzájuk célállapotot.

    Ha ez a döntés megszületik, ez a teszt bukik -- és ez a szándék.
    """
    for akcio in SPECIFIKACIORA_VARO_AKCIOK:
        assert all(
            next_state(allapot, akcio) is None for allapot in CareerState
        )
