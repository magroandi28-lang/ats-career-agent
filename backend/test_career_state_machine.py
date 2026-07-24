"""A karrierfolyamat determinisztikus szabályainak tesztjei."""

from backend.career_state_machine import (
    CareerAction,
    CareerIntent,
    CareerState,
    allowed_actions,
    confirm_intent_transition,
    next_state,
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
