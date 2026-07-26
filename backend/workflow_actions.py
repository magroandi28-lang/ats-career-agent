"""A karrierfolyamat műveleteinek végrehajtása.

A folyamat gerince: az állapotgép eldönti, hogy egy művelet az adott
állapotból egyáltalán indítható-e, ez a modul pedig lefuttatja a hozzá
tartozó modult és megmondja, milyen GPS-nyomot hagy maga után.

Vezérlési elv (docs/felhasznaloi-allapotgep.md 2./3. pont): az LLM sosem
hajt végre műveletet, csak javasol. Ide kizárólag kifejezett felhasználói
művelet érkezhet, és minden végrehajtás előtt a `next_state()` kapuján
kell átmennie.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final

from backend.career_state_machine import CareerAction
from backend.gps_vocabulary import ellenorzott_esemeny, ellenorzott_snapshot
from backend.profile_service import confirmed_values
from utils.adatbazis import kereslet_korkep, ksh_kereset, szakma_statisztika


class ActionError(RuntimeError):
    """A művelet nem hajtható végre; a szöveg a felhasználónak szól."""


class GpsNyomHiba(ValueError):
    """Hiányos GPS-nyom -- programozói hiba, nem felhasználói."""


@dataclass(frozen=True)
class ActionContext:
    """Minden, amit egy művelet a végrehajtáshoz megkaphat.

    A művelet szándékosan nem kap adatbázis-klienst és nem ír állapotot:
    az állapotmentés a hívó orchestrator (main.py) dolga.
    """

    user_id: str
    workflow: dict
    profile: dict
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ActionOutcome:
    """A művelet eredménye és az általa indokolt GPS-nyom."""

    result: dict
    gps_esemeny: str | None = None
    gps_terulet: str | None = None
    gps_allapot: str | None = None
    context_patch: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.gps_esemeny is not None:
            ellenorzott_esemeny(self.gps_esemeny)
        if self.gps_terulet is not None or self.gps_allapot is not None:
            if not (self.gps_terulet and self.gps_allapot):
                raise GpsNyomHiba(
                    "A GPS-nyomhoz terület és állapot is kell."
                )
            ellenorzott_snapshot(self.gps_terulet, self.gps_allapot)


def _celmunkakor(ctx: ActionContext) -> str:
    """A megerősített célmunkakör; enélkül nincs mihez viszonyítani.

    Kizárólag megerősített profiladatból dolgozunk: a vázlat még nem tény
    (docs/felhasznaloi-allapotgep.md 5. elfogadási feltétel).
    """
    ertekek = confirmed_values(ctx.profile)
    szakma = str(ertekek.get("target_role") or "").strip()
    if not szakma:
        raise ActionError(
            "Ehhez a lépéshez előbb erősítsd meg a célmunkakörödet."
        )
    return szakma


def _piaci_korkep_inditasa(ctx: ActionContext) -> ActionOutcome:
    """Dátumozott, forrásolt piaci összevetés a saját adatbázisunkból.

    Nulla modellhívás: a hirdetésszám, a készséggyakoriság és a bérsávok
    mind mért adatok. A KSH-átlagkereset csak akkor kerül bele, ha a
    foglalkozásnév ténylegesen illeszkedik -- becslést nem gyártunk.
    """
    szakma = _celmunkakor(ctx)
    statisztika = szakma_statisztika(szakma)
    korkep = kereslet_korkep()
    sajat_kereslet = next(
        (sor for sor in korkep if sor["szakma"].casefold() == szakma.casefold()),
        None,
    )

    if not statisztika and sajat_kereslet is None:
        raise ActionError(
            f"A(z) „{szakma}” szakmáról még nincs elég saját piaci adatunk."
        )

    return ActionOutcome(
        result={
            "szakma": szakma,
            "kereslet": sajat_kereslet,
            "hirdetesek_szama": statisztika.get("hirdetesek_szama", 0),
            "keszsegek": (statisztika.get("keszsegek") or [])[:10],
            "bersavok": (statisztika.get("bersavok") or [])[:5],
            "ksh_atlagkereset": ksh_kereset(szakma),
            "osszehasonlitott_szakmak": len(korkep),
        },
        gps_esemeny="market_snapshot_ready",
        gps_terulet="piaci_kep",
        gps_allapot="betoltve",
        context_patch={"piaci_kep_szakma": szakma},
    )


Handler = Callable[[ActionContext], ActionOutcome]

# A regiszterben szereplő műveletek hajthatók végre. Ami nincs benne, arra a
# végpont 501-et ad: az állapotgép ismeri az átmenetet, de a modul még nem
# készült el. Ez szándékosan megkülönböztethető a 409-től, ami azt jelenti,
# hogy a művelet ebből az állapotból nem is lenne szabad.
ACTION_HANDLERS: Final[dict[CareerAction, Handler]] = {
    CareerAction.PIACI_KORKEP_INDITASA: _piaci_korkep_inditasa,
}


def vegrehajthato(action: CareerAction) -> bool:
    return action in ACTION_HANDLERS


def execute_action(action: CareerAction, ctx: ActionContext) -> ActionOutcome:
    handler = ACTION_HANDLERS.get(action)
    if handler is None:
        raise NotImplementedError(f"Nincs végrehajtó a művelethez: {action}")
    return handler(ctx)
