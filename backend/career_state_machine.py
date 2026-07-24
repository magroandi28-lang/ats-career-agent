"""A kanonikus karrierfolyamat determinisztikus állapotgépe.

Az LLM csak szándékot és következő műveletet javasol. E modul dönti el,
hogy az aktuális állapotból a javaslat végrehajtható-e.
"""

from enum import StrEnum
from typing import Final


RULE_VERSION: Final = "career-state-v1"


class CareerIntent(StrEnum):
    CV_ELLENORZES = "cv_ellenorzes"
    CV_FRISSITES = "cv_frissites"
    CV_KESZITES = "cv_keszites"
    ALLAS_KERESES = "allas_kereses"
    KONKRET_PALYAZAS = "konkret_palyazas"
    TANACSADAS = "tanacsadas"
    PALYAVALTAS = "palyavaltas"
    PIACI_KORKEP = "piaci_korkep"
    KEPZES_KERESES = "kepzes_kereses"
    PORTFOLIO = "portfolio"
    BIZONYTALAN = "bizonytalan"


class CareerState(StrEnum):
    CEL_TISZTAZATLAN = "CEL_TISZTAZATLAN"
    CEL_TISZTAZOTT = "CEL_TISZTAZOTT"
    PROFIL_HIANYOS = "PROFIL_HIANYOS"
    PROFIL_ELLENORZOTT = "PROFIL_ELLENORZOTT"
    TANACSADAS_AKTIV = "TANACSADAS_AKTIV"
    PIACI_KEP_KESZ = "PIACI_KEP_KESZ"
    CV_TERVEZET = "CV_TERVEZET"
    CV_JOVAHAGYOTT = "CV_JOVAHAGYOTT"
    ALLASKERESES_AKTIV = "ALLASKERESES_AKTIV"
    ALLASOK_BEMUTATVA = "ALLASOK_BEMUTATVA"
    ALLAS_KIVALASZTVA = "ALLAS_KIVALASZTVA"
    HIRDETES_ELLENORZOTT = "HIRDETES_ELLENORZOTT"
    ATS_KESZ = "ATS_KESZ"
    PALYAZATI_CSOMAG_TERVEZET = "PALYAZATI_CSOMAG_TERVEZET"
    KULDESRE_JOVAHAGYVA = "KULDESRE_JOVAHAGYVA"
    PALYAZAS_ELINDITVA = "PALYAZAS_ELINDITVA"
    PALYAZAS_BEADVA_NAPLOZVA = "PALYAZAS_BEADVA_NAPLOZVA"


class CareerAction(StrEnum):
    TISZTAZO_KERDES = "tisztazo_kerdes"
    CEL_MEGEROSITESE = "cel_megerositese"
    PROFIL_ADATOK_BEKERESE = "profil_adatok_bekerese"
    PROFIL_MEGEROSITESE = "profil_megerositese"
    TANACSADAS_INDITASA = "tanacsadas_inditasa"
    PIACI_KORKEP_INDITASA = "piaci_korkep_inditasa"
    CV_ELLENORZES_INDITASA = "cv_ellenorzes_inditasa"
    CV_FRISSITES_INDITASA = "cv_frissites_inditasa"
    CV_KESZITES_INDITASA = "cv_keszites_inditasa"
    ALLASKERESES_INDITASA = "allaskereses_inditasa"
    HIRDETES_BEOLVASASA = "hirdetes_beolvasasa"
    PALYAZAS_INDITASA = "palyazas_inditasa"
    KEPZES_KERESES_INDITASA = "kepzes_kereses_inditasa"
    PORTFOLIO_INDITASA = "portfolio_inditasa"


INTENT_START_ACTION: Final[dict[CareerIntent, CareerAction]] = {
    CareerIntent.CV_ELLENORZES: CareerAction.CV_ELLENORZES_INDITASA,
    CareerIntent.CV_FRISSITES: CareerAction.CV_FRISSITES_INDITASA,
    CareerIntent.CV_KESZITES: CareerAction.CV_KESZITES_INDITASA,
    CareerIntent.ALLAS_KERESES: CareerAction.ALLASKERESES_INDITASA,
    CareerIntent.KONKRET_PALYAZAS: CareerAction.HIRDETES_BEOLVASASA,
    CareerIntent.TANACSADAS: CareerAction.TANACSADAS_INDITASA,
    CareerIntent.PALYAVALTAS: CareerAction.TANACSADAS_INDITASA,
    CareerIntent.PIACI_KORKEP: CareerAction.PIACI_KORKEP_INDITASA,
    CareerIntent.KEPZES_KERESES: CareerAction.KEPZES_KERESES_INDITASA,
    CareerIntent.PORTFOLIO: CareerAction.PORTFOLIO_INDITASA,
}


TRANSITIONS: Final[dict[tuple[CareerState, CareerAction], CareerState]] = {
    (CareerState.CEL_TISZTAZATLAN, CareerAction.CEL_MEGEROSITESE):
        CareerState.CEL_TISZTAZOTT,
    (CareerState.CEL_TISZTAZOTT, CareerAction.PROFIL_ADATOK_BEKERESE):
        CareerState.PROFIL_HIANYOS,
    (CareerState.PROFIL_HIANYOS, CareerAction.PROFIL_MEGEROSITESE):
        CareerState.PROFIL_ELLENORZOTT,
    (CareerState.CEL_TISZTAZOTT, CareerAction.PROFIL_MEGEROSITESE):
        CareerState.PROFIL_ELLENORZOTT,
    (CareerState.PROFIL_ELLENORZOTT, CareerAction.TANACSADAS_INDITASA):
        CareerState.TANACSADAS_AKTIV,
    (CareerState.PROFIL_ELLENORZOTT, CareerAction.PIACI_KORKEP_INDITASA):
        CareerState.PIACI_KEP_KESZ,
    (CareerState.PROFIL_ELLENORZOTT, CareerAction.CV_ELLENORZES_INDITASA):
        CareerState.CV_TERVEZET,
    (CareerState.PROFIL_ELLENORZOTT, CareerAction.CV_FRISSITES_INDITASA):
        CareerState.CV_TERVEZET,
    (CareerState.PROFIL_ELLENORZOTT, CareerAction.CV_KESZITES_INDITASA):
        CareerState.CV_TERVEZET,
    (CareerState.PROFIL_ELLENORZOTT, CareerAction.ALLASKERESES_INDITASA):
        CareerState.ALLASKERESES_AKTIV,
    (CareerState.PROFIL_ELLENORZOTT, CareerAction.HIRDETES_BEOLVASASA):
        CareerState.HIRDETES_ELLENORZOTT,
}


def allowed_actions(state: CareerState) -> tuple[CareerAction, ...]:
    """Visszaadja az állapotban technikailag engedélyezett műveleteket."""
    actions = [action for (source, action), _ in TRANSITIONS.items() if source == state]
    if state == CareerState.CEL_TISZTAZATLAN:
        actions.append(CareerAction.TISZTAZO_KERDES)
    return tuple(dict.fromkeys(actions))


def intent_is_confirmable(intent: CareerIntent) -> bool:
    return intent is not CareerIntent.BIZONYTALAN


def confirm_intent_transition(
    state: CareerState,
    intent: CareerIntent,
) -> CareerState | None:
    """A szándék megerősítése csak a tisztázatlan célállapotból lehetséges."""
    if state != CareerState.CEL_TISZTAZATLAN or not intent_is_confirmable(intent):
        return None
    return TRANSITIONS[(state, CareerAction.CEL_MEGEROSITESE)]


def next_state(state: CareerState, action: CareerAction) -> CareerState | None:
    """Nincs hallgatólagos átmenet: tiltott párra None érkezik."""
    return TRANSITIONS.get((state, action))


def start_action_for_intent(intent: CareerIntent) -> CareerAction | None:
    return INTENT_START_ACTION.get(intent)
