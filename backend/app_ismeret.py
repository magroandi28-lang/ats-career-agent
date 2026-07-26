# -*- coding: utf-8 -*-
"""Flow alkalmazás-ismerete, szerveroldalról.

A terv 7. pontja „rövid, verziózott alkalmazás-ismeretet" ír elő Flow
bemenetében. Ez eddig két beégetett sor volt a frontendben, amit ráadásul
a böngésző küldött -- tehát bárki átírhatta volna.

Innentől a szerver adja, a `docs/flow_app_ismeret.md` fájlból, és a
kliens által küldött értéket figyelmen kívül hagyjuk.
"""

from functools import lru_cache
from pathlib import Path
from typing import Final

from backend.career_state_machine import CareerState, allowed_actions
from backend.workflow_actions import vegrehajthato


ISMERET_FAJL: Final = (
    Path(__file__).resolve().parents[1] / "docs" / "flow_app_ismeret.md"
)

# Ha a dokumentum bővül, ezt kell emelni: így a naplóból visszakereshető,
# melyik változattal dolgozott Flow egy adott válasznál.
ISMERET_VERZIO: Final = "app-ismeret-v1"

MAX_KARAKTER: Final = 6000


@lru_cache
def alkalmazas_ismeret() -> str:
    """A dokumentum tartalma, egyszer beolvasva.

    Hiányzó fájl nem áll meg a folyamatot: Flow ilyenkor kevesebbet tud,
    de válaszol. A hiány a naplóban látszik.
    """
    try:
        szoveg = ISMERET_FAJL.read_text(encoding="utf-8").strip()
    except OSError as exc:
        print(f"[app_ismeret] A leírás nem olvasható: {exc}")
        return ""
    return szoveg[:MAX_KARAKTER]


def elerheto_lepesek(state: CareerState) -> list[str]:
    """Amit Flow ebben az állapotban ténylegesen el tud indítani.

    Kódból származik, nem kézzel karbantartott listából -- így nem tud
    elcsúszni attól, ami valóban be van kötve.
    """
    return [
        akcio.value for akcio in allowed_actions(state) if vegrehajthato(akcio)
    ]
