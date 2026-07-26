"""A kanonikus karrierfolyamat determinisztikus állapotgépe.

Az LLM csak szándékot és következő műveletet javasol. E modul dönti el,
hogy az aktuális állapotból a javaslat végrehajtható-e.
"""

from enum import StrEnum
from typing import Final


RULE_VERSION: Final = "career-state-v2"


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
    CV_JOVAHAGYASA = "cv_jovahagyasa"
    ALLASKERESES_INDITASA = "allaskereses_inditasa"
    ALLASOK_BEMUTATASA = "allasok_bemutatasa"
    ALLAS_KIVALASZTASA = "allas_kivalasztasa"
    HIRDETES_BEOLVASASA = "hirdetes_beolvasasa"
    PALYAZAS_INDITASA = "palyazas_inditasa"
    ATS_ELEMZES_INDITASA = "ats_elemzes_inditasa"
    PALYAZATI_CSOMAG_KESZITESE = "palyazati_csomag_keszitese"
    CSOMAG_JOVAHAGYASA = "csomag_jovahagyasa"
    KULSO_MUVELET_INDITASA = "kulso_muvelet_inditasa"
    BEADAS_IGAZOLASA = "beadas_igazolasa"
    KEPZES_KERESES_INDITASA = "kepzes_kereses_inditasa"
    PORTFOLIO_INDITASA = "portfolio_inditasa"


class GlobalAction(StrEnum):
    """Bármely állapotból elérhető kilépések (felhasznaloi-allapotgep.md 5.).

    Ezek szándékosan nem részei a `TRANSITIONS` gráfnak: nem a folyamat
    előrehaladását jelentik, hanem a felhasználó kifejezett visszalépését.
    """

    CEL_MODOSITASA = "cel_modositasa"
    PROFIL_VALTOZOTT = "profil_valtozott"
    FELADAT_MEGSZAKITASA = "feladat_megszakitasa"


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

    # CV-ág lezárása: tervezetből csak kifejezett jóváhagyással lesz
    # használható verzió (felhasznaloi-allapotgep.md 6.).
    (CareerState.CV_TERVEZET, CareerAction.CV_JOVAHAGYASA):
        CareerState.CV_JOVAHAGYOTT,
    (CareerState.CV_JOVAHAGYOTT, CareerAction.ALLASKERESES_INDITASA):
        CareerState.ALLASKERESES_AKTIV,

    # Álláskeresési ág. A találat megjelenítése külön lépés: a keresés
    # lefutása önmagában még nem eredmény (7. pont).
    (CareerState.ALLASKERESES_AKTIV, CareerAction.ALLASOK_BEMUTATASA):
        CareerState.ALLASOK_BEMUTATVA,
    (CareerState.ALLASOK_BEMUTATVA, CareerAction.ALLAS_KIVALASZTASA):
        CareerState.ALLAS_KIVALASZTVA,
    (CareerState.ALLAS_KIVALASZTVA, CareerAction.PALYAZAS_INDITASA):
        CareerState.HIRDETES_ELLENORZOTT,

    # Pályázási ág. Az ATS csak ellenőrzött konkrét hirdetésből indulhat
    # (12. pont, 4. elfogadási feltétel).
    (CareerState.HIRDETES_ELLENORZOTT, CareerAction.ATS_ELEMZES_INDITASA):
        CareerState.ATS_KESZ,
    (CareerState.ATS_KESZ, CareerAction.PALYAZATI_CSOMAG_KESZITESE):
        CareerState.PALYAZATI_CSOMAG_TERVEZET,
    (CareerState.PALYAZATI_CSOMAG_TERVEZET, CareerAction.CSOMAG_JOVAHAGYASA):
        CareerState.KULDESRE_JOVAHAGYVA,
    (CareerState.KULDESRE_JOVAHAGYVA, CareerAction.KULSO_MUVELET_INDITASA):
        CareerState.PALYAZAS_ELINDITVA,
    (CareerState.PALYAZAS_ELINDITVA, CareerAction.BEADAS_IGAZOLASA):
        CareerState.PALYAZAS_BEADVA_NAPLOZVA,
}


GLOBAL_TRANSITIONS: Final[dict[GlobalAction, CareerState]] = {
    GlobalAction.CEL_MODOSITASA: CareerState.CEL_TISZTAZOTT,
    GlobalAction.PROFIL_VALTOZOTT: CareerState.PROFIL_HIANYOS,
    GlobalAction.FELADAT_MEGSZAKITASA: CareerState.CEL_TISZTAZATLAN,
}


# A kanonikus terv (felhasznaloi-allapotgep.md 4. és 9.) a képzés- és
# portfólió-utat visszatérő körként írja le, de nem nevez meg hozzájuk
# célállapotot. Amíg ez a döntés nincs meg, ezek az akciók szándékosan nem
# vezetnek átmenethez -- így a hiány látható és tesztelhető, nem csendes
# zsákutca egy nem várt `None` visszatérésben.
SPECIFIKACIORA_VARO_AKCIOK: Final[frozenset[CareerAction]] = frozenset({
    CareerAction.KEPZES_KERESES_INDITASA,
    CareerAction.PORTFOLIO_INDITASA,
})

TERMINAL_STATE: Final = CareerState.PALYAZAS_BEADVA_NAPLOZVA


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


def global_next_state(action: GlobalAction) -> CareerState:
    """A felhasználó kifejezett visszalépése bármely állapotból érvényes."""
    return GLOBAL_TRANSITIONS[action]


def reachable_states() -> frozenset[CareerState]:
    """A kezdőállapotból ténylegesen bejárható állapotok halmaza.

    Az átmeneti gráf szélességi bejárása. Azért van kódban és nem csak
    tesztben, mert így egy új állapot bevezetésekor azonnal kiderül, ha
    nem vezet hozzá út.
    """
    elert = {CareerState.CEL_TISZTAZATLAN}
    hatar = [CareerState.CEL_TISZTAZATLAN]
    while hatar:
        allapot = hatar.pop()
        for (forras, _), cel in TRANSITIONS.items():
            if forras is allapot and cel not in elert:
                elert.add(cel)
                hatar.append(cel)
    return frozenset(elert)
