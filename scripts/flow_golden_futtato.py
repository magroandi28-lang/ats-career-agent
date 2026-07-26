# -*- coding: utf-8 -*-
"""A golden set élő rétege: valódi modellhívásokkal méri Flow-t.

Ez PÉNZBE KERÜL (esetenként egy modellhívás), ezért nem a CI futtatja,
hanem te, kézzel -- tipikusan prompt-módosítás előtt és után, hogy lásd,
javítottál-e vagy rontottál.

Futtatás a projekt gyökeréből:

    python scripts/flow_golden_futtato.py

Csak a szándékfelismerést és a javasolt művelet szabályosságát méri. Azt,
hogy tiltott műveletet nem lehet végrehajtani, a backend/test_flow_golden.py
bizonyítja ingyen -- ez itt azt nézi, mennyire jól ért Flow.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.career_state_machine import allowed_actions  # noqa: E402
from backend.golden_flow import ESETEK, GOLDEN_VERZIO  # noqa: E402
from utils.flow_agy import flow_dontes  # noqa: E402


def _jeloles(rendben: bool) -> str:
    return "OK  " if rendben else "HIBA"


def main() -> int:
    if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        print("Nincs modellkulcs a környezetben (GEMINI_API_KEY vagy OPENAI_API_KEY).")
        print("A .env fájlban kell lennie, vagy a shellben exportálva.")
        return 2

    # A Gemini ingyenes kerete percenként 20 hívás. Egy eset hibás válasz
    # esetén kétszer próbálkozik, ezért esetenként legfeljebb két hívással
    # számolunk. A szünet nélkül a futás 429-be fut, és minden eredmény
    # hamis lesz -- ez a mérés értelmét venné el.
    szunet = float(os.environ.get("GOLDEN_SZUNET_MP", "7"))
    becsult_perc = round(len(ESETEK) * szunet / 60, 1)

    print(f"Flow golden set — {GOLDEN_VERZIO}")
    print(f"{len(ESETEK)} eset, esetenként egy modellhívás.")
    print(f"Szünet a hívások közt: {szunet:g} mp (ingyenes keret miatt).")
    print(f"Várható futásidő: kb. {becsult_perc:g} perc.\n")

    hibak: list[str] = []
    intent_talalat = 0
    intent_merve = 0
    kvotahiba = 0

    for sorszam, eset in enumerate(ESETEK):
        if sorszam:
            time.sleep(szunet)
        dontes = flow_dontes(
            eset.uzenet,
            {},
            "A Karrier-Ügynökség karrierprofilt, piaci körképet, "
            "állásillesztést és pályázati anyagokat készít.",
            [],
            current_state=eset.allapot,
        )

        sorhibak: list[str] = []

        # A tartalékválasz pontosan így néz ki. Ha ezt kapjuk, a modell meg
        # sem szólalt (kvótahiba vagy hálózati gond) -- ilyenkor a mérés nem
        # Flow-ról szól, és ezt külön kell jelezni, nem szándékhibaként.
        if dontes.confidence == 0.0 and dontes.response_message.startswith(
            "Nem sikerült pontosan értelmeznem"
        ):
            kvotahiba += 1
            print(f"NINCS {eset.azonosito}  (a modell nem válaszolt)")
            continue

        if eset.vart_intent is not None:
            intent_merve += 1
            if dontes.intent is eset.vart_intent:
                intent_talalat += 1
            else:
                sorhibak.append(
                    f"szándék: várt {eset.vart_intent.value}, kapott {dontes.intent.value}"
                )

        if dontes.proposed_action is not None:
            if dontes.proposed_action in eset.tiltott_akciok:
                sorhibak.append(f"TILTOTT műveletet javasolt: {dontes.proposed_action.value}")
            elif dontes.proposed_action not in allowed_actions(eset.allapot):
                sorhibak.append(
                    f"az állapotban nem engedélyezett műveletet javasolt: "
                    f"{dontes.proposed_action.value}"
                )

        if not dontes.response_message.strip():
            sorhibak.append("üres válaszszöveg")

        print(f"{_jeloles(not sorhibak)} {eset.azonosito}")
        for hiba in sorhibak:
            print(f"       - {hiba}")
            hibak.append(f"{eset.azonosito}: {hiba}")

    print()
    if kvotahiba:
        print(
            f"FIGYELEM: {kvotahiba} esetben a modell meg sem szólalt "
            "(kvóta vagy hálózat). Ezek az eredmények nem Flow-ról szólnak."
        )
        print("Növeld a szünetet: GOLDEN_SZUNET_MP=12 python scripts/flow_golden_futtato.py\n")
    if intent_merve:
        arany = round(100 * intent_talalat / intent_merve)
        print(f"Szándékfelismerés: {intent_talalat}/{intent_merve} ({arany}%)")
    print(f"Szabálysértés: {len(hibak)} db")

    if hibak:
        print("\nAmit javítani kell:")
        for hiba in hibak:
            print(f"  - {hiba}")
        return 1

    print("\nMinden eset rendben.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
