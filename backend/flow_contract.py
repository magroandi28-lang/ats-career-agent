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

# Zárt szándék-enum -- a terv "engedélyezett szándék-enumot ad" elvárása.
FlowIntent = Literal[
    "allast_keres_van_cv",
    "allast_keres_nincs_cv",
    "palyavaltas",
    "altalanos_kerdes",
    "bizonytalan",
]

# Zárt akció-enum -- egyelőre egyetlen engedélyezett automatikus akció van
# (a Karrier Ügynök lánc indítása); a többi programozási csomaggal bővül.
FlowAction = Literal["karrier_ugynok_inditasa"]

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

    intent: FlowIntent
    response_message: str = Field(min_length=1, max_length=2000)
    proposed_action: Optional[FlowAction] = None
    required_fields: list[str] = Field(default_factory=list)
    specialist_request: Optional[FlowSpecialista] = None
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    szakma: str = Field(default="", max_length=200)


def biztonsagos_alapertelmezes(uzenet: str) -> FlowDecision:
    """Fallback, ha a modell nem adott séma szerinti választ (két kísérlet
    után sem). A terv 8. pontja szerint: "Hibás agent-JSON: egyszeri
    javítási kísérlet, majd biztonságos fallback" — ez az a fallback."""
    return FlowDecision(
        intent="bizonytalan",
        response_message=uzenet,
        confidence=0.0,
    )
