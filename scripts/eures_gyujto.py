# -*- coding: utf-8 -*-
"""EURES-HU gyűjtő — scripts/eures_gyujto.py

A hazai (magyarországi) hirdetéseket EGÉSZÍTI KI a Jooble mellett: az EURES
nyilvános API-ja a magyar állami foglalkoztatási szolgálat (NFSZ) hirdetéseit
is tartalmazza — ez STRUKTURÁLISAN MÁS forrás, mint a Jooble (kereskedelmi
portálok: profession.hu, CV Online stb.), ezért nem duplikál, hanem bővíti
a lefedettséget (élőben ellenőrizve: azonos cégnevek nem szerepeltek még
a cegek táblában).

Ugyanazt a szakmalistát dolgozza fel, mint a Jooble-gyűjtő (import onnan),
és UGYANABBA a hirdetesek táblába ment, forras_tipus='eures' jelöléssel.

ELŐFELTÉTEL: db/feor_lista.sql UTÁN futtatandó SQL migráció szükséges —
lásd a forras_tipus check constraint bővítését (lentebb a fájl végén, ill.
a chatben kapott SQL-parancs).

Futtatás a projekt gyökeréből:
    python scripts/eures_gyujto.py                   # a teljes szakmalista
    python scripts/eures_gyujto.py "villanyszerelő"   # csak egy szakma

Nincs AI-hívás a kereséshez (ingyenes, kulcs nélküli EURES API). A készség-
kinyerés a Jooble-gyűjtővel MEGEGYEZŐEN a Google Gemini ingyenes szintjét
használja (közös napi keret — lásd a Gemini-kvóta megjegyzést lentebb).

Később GitHub Actions futtatja majd naponta, a Jooble-gyűjtő után —
addig kézzel indítod.
"""

import os
import sys
import time

# A projekt gyökerét és a scripts/ mappát is a path-ra tesszük, hogy az
# utils/agents importok és a jooble_gyujto.py-ból való újrafelhasználás működjön.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.adatbazis import (  # noqa: E402
    gyujtes_mentese,
    keszsegnev_normalizalas,
    kliens,
    letezo_linkek,
)
from utils.eures import eures_kereses  # noqa: E402
from jooble_gyujto import SZAKMAK, keszsegek_kinyerese  # noqa: E402

DARAB = 50          # EURES lapméret-korlátja (élőben ellenőrizve: 100 = 0 találat)
CSOMAG_MERET = 10   # ennyit adunk egyszerre a készség-kinyerőnek


def szakma_gyujtes(szakma: str, kategoria: str) -> int:
    """Egy szakma teljes feldolgozása: EURES-keresés (csak HU) →
    duplikátum-szűrés → készség-kinyerés → mentés. Az új hirdetések számát
    adja vissza."""
    print(f"\n=== {szakma} ===")
    talalat = eures_kereses(szakma, ["hu"], darab=DARAB)
    if not talalat["ok"]:
        print(f"  EURES hiba: {talalat['hiba']}")
        return 0

    allasok = [{
        "cim": a["cim"],
        "ceg": a["munkaado"],
        "snippet": a["leiras"],
        "link": a["link"],
        "helyszin": "",  # az EURES csak ország-szintű adatot ad, várost nem — nem találjuk ki
        "datum": a["datum"],
        "bersav": "",
        "forras_tipus": "eures",
    } for a in talalat["allasok"] if a["cim"]]
    print(f"  EURES talalat: {talalat['talalatok']} (letoltve: {len(allasok)})")
    if not allasok:
        return 0

    # Duplikátum-szűrés MÉG a készség-kinyerés előtt (Gemini-kvóta kímélése) —
    # ugyanaz a link-alapú ellenőrzés, mint a Jooble-gyűjtőnél.
    megvan = letezo_linkek([a["link"] for a in allasok])
    ujak = [a for a in allasok if a["link"] not in megvan]
    print(f"  Ebbol uj (meg nincs az adatbazisban): {len(ujak)}")
    if not ujak:
        return 0

    szakma_info = {"szakma": szakma, "szakma_kategoria": kategoria}
    mentve = 0
    for i in range(0, len(ujak), CSOMAG_MERET):
        csomag = ujak[i:i + CSOMAG_MERET]
        keszsegek = keszsegek_kinyerese(csomag)
        mentve += gyujtes_mentese(szakma_info, csomag, keszsegek)
        time.sleep(5)  # a Gemini ingyenes szint perc-limitje miatt
    return mentve


def main():
    if kliens() is None:
        print("HIBA: a Supabase kapcsolat nincs beallitva (.env)!")
        return

    lista = [(sys.argv[1], "Egyéb")] if len(sys.argv) > 1 else SZAKMAK

    print(f"EURES-HU gyujto indul — {len(lista)} szakma")
    osszes = 0
    for szakma, kategoria in lista:
        try:
            osszes += szakma_gyujtes(szakma, kategoria)
        except Exception as e:
            print(f"  VARATLAN HIBA ({szakma}): {e} — megyunk tovabb.")
        time.sleep(1)  # kimeletes tempo az EURES publikus vegpontja fele

    keszsegnev_normalizalas()
    print(f"\nKESZ! Osszesen {osszes} uj hirdetes mentve (EURES-HU).")


if __name__ == "__main__":
    main()
