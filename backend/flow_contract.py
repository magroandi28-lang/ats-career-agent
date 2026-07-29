# -*- coding: utf-8 -*-
"""Flow strukturált döntési szerződése — a 02-flow-career-gps.md terv 4. és
10. pontja alapján.

A terv kimondja: "A jelenlegi szabad szöveges [FLOW_AKCIO: ...] jelölések és
regex-alapú vezérlés megszűnnek" és "Szabad szöveges action-tag vagy regex
nem vezérelhet funkciót." Ez a fájl az a szerződés, ami ezt felváltja: Flow
KIZÁRÓLAG ezt a szerkezetet adhatja vissza. Ha a modell válasza nem
illeszkedik rá, a döntés nem hajtható végre — nincs "majdnem jó" JSON.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.career_state_machine import CareerAction, CareerIntent

# A README.md 3. pontjában rögzített három specialista (Flow Manager saját
# magát nem kérheti fel).
FlowSpecialista = Literal[
    "career_advisor",
    "application_materials_agent",
    "portfolio_designer",
]


class FlowDecision(BaseModel):
    """Flow Manager egyetlen érvényes kimeneti formája.

    A mezők jelentése a tervből:
    - intent: mit ismert fel a felhasználó szándékából.
    - response_message: a felhasználónak megjelenő, közérthető szöveg.
    - proposed_action: engedélyezett automatikus művelet vagy None.
    - required_fields: mely mezők hiányoznak még a döntéshez (pl. "szakma").
    - specialist_request: melyik specialistát kéri fel Flow, vagy None.
    - evidence_refs: mely tudásanyag-/profilhivatkozásokra épített.
    - confidence: 0..1, a szándékfelismerés bizonyossága.
    - szakma: csak akkor töltött, ha proposed_action karrier_ugynok_inditasa.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    intent: CareerIntent
    response_message: str = Field(min_length=1, max_length=2000)
    proposed_action: Optional[CareerAction] = None
    required_fields: list[str] = Field(default_factory=list)
    specialist_request: Optional[FlowSpecialista] = None
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    szakma: str = Field(default="", max_length=200)

    # VÁLASZLEHETŐSÉGEK: Flow kérdezhet gombokkal.
    #
    # Eddig a felületen állandó kártyarács állt, amiből a felhasználónak
    # kellett kiválasztania, melyik folyamatban van. Ez menü, nem
    # beszélgetés -- és mérve zavaró volt: a CV-átvizsgálás közben három
    # további kártya jelent meg.
    #
    # Ezzel Flow maga tesz fel kérdést, és MELLÉ adja a lehetséges
    # válaszokat. A gombra kattintás ugyanaz, mintha a felhasználó beírta
    # volna: nem indít műveletet, csak választ. A művelet továbbra is az
    # állapotgép kapuján megy át.
    #
    # Legfeljebb három, mert egy kérdésre ennél több választ senki nem
    # olvas el. A szabad szöveges válasz mindig marad.
    valaszlehetosegek: list[str] = Field(default_factory=list, max_length=3)


def biztonsagos_alapertelmezes(uzenet: str) -> FlowDecision:
    """Fallback, ha a modell nem adott séma szerinti választ (két kísérlet
    után sem). A terv 8. pontja szerint: "Hibás agent-JSON: egyszeri
    javítási kísérlet, majd biztonságos fallback" — ez az a fallback."""
    return FlowDecision(
        intent=CareerIntent.BIZONYTALAN,
        response_message=uzenet,
        proposed_action=CareerAction.TISZTAZO_KERDES,
        confidence=0.0,
    )
