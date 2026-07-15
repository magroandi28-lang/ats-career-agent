# -*- coding: utf-8 -*-
"""Jooble állásgyűjtő — scripts/jooble_gyujto.py (3. fázis)

Önállóan futtatható gyűjtő: a SZAKMAK listán végigmegy, a Jooble API-ból
lehúzza a friss hirdetéseket, a Haiku kinyeri a készségeket, és minden
a Supabase-be kerül. Duplikátumot nem dolgoz fel kétszer (se pénzt,
se időt nem pazarol rá).

Futtatás a projekt gyökeréből:
    python scripts/jooble_gyujto.py                  # a teljes szakmalista
    python scripts/jooble_gyujto.py "bolti eladó"    # csak egy szakma

Később GitHub Actions futtatja majd naponta — addig kézzel indítod.
"""

import os
import re
import sys
import time

import requests
from dotenv import load_dotenv

# A projekt gyökerét a path-ra tesszük, hogy az agents/utils importok működjenek
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.karrier_ugynok import keszsegek_kinyerese  # noqa: E402
from utils.adatbazis import gyujtes_mentese, kliens, letezo_linkek  # noqa: E402

load_dotenv()

JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY", "")
JOOBLE_URL = "https://hu.jooble.org/api/"

# ── GYŰJTÖTT SZAKMÁK (név, kategória) — bővítsd bátran! ──────
SZAKMAK = [
    # Kereskedelem, vendéglátás
    ("bolti eladó", "Kereskedelem"),
    ("pénztáros", "Kereskedelem"),
    ("raktáros", "Kereskedelem"),
    ("szakács", "Szolgáltatás"),
    ("felszolgáló", "Szolgáltatás"),
    # Iroda, ügyfélkapcsolat
    ("ügyfélszolgálati munkatárs", "Szolgáltatás"),
    ("adminisztratív asszisztens", "Szolgáltatás"),
    ("könyvelő", "Szolgáltatás"),
    # Ipar, műszaki
    ("villanyszerelő", "Ipar"),
    ("karbantartó", "Ipar"),
    ("gépkezelő", "Ipar"),
    ("sofőr", "Szolgáltatás"),
    # Egészségügy
    ("ápoló", "Egészségügy"),
    # IT
    ("szoftvertesztelő", "IT"),
    ("Python fejlesztő", "IT"),
    ("AI mérnök", "IT"),
    ("adatelemző", "IT"),
]

HELYSZIN = ""                    # üres = egész Magyarország (lehet pl. "Budapest")
MAX_HIRDETES_SZAKMANKENT = 20    # ennyi friss hirdetést nézünk szakmánként
CSOMAG_MERET = 10                # ennyit adunk egyszerre a készség-kinyerőnek


def _tisztit(szoveg: str) -> str:
    """HTML-tagek és felesleges szóközök eltávolítása a Jooble mezőkből."""
    szoveg = re.sub(r"<[^>]+>", " ", szoveg or "")
    szoveg = szoveg.replace("&nbsp;", " ").replace("&amp;", "&")
    return " ".join(szoveg.split())


def jooble_kereses(szakma: str) -> list:
    """Egy szakma friss hirdetései a Jooble API-ból, egységes formára hozva."""
    try:
        r = requests.post(
            JOOBLE_URL + JOOBLE_API_KEY,
            json={"keywords": szakma, "location": HELYSZIN},
            timeout=20,
        )
        r.raise_for_status()
        jobs = r.json().get("jobs", [])
    except Exception as e:
        print(f"  Jooble hiba ({szakma}): {e}")
        return []

    allasok = []
    for j in jobs[:MAX_HIRDETES_SZAKMANKENT]:
        cim = _tisztit(j.get("title", ""))
        if not cim:
            continue
        allasok.append({
            "cim": cim,
            "ceg": _tisztit(j.get("company", "")),
            "snippet": _tisztit(j.get("snippet", ""))[:500],
            "link": (j.get("link") or "").strip(),
            "helyszin": _tisztit(j.get("location", "")),
            "datum": (j.get("updated") or "")[:10],
            "bersav": _tisztit(j.get("salary", "")),
            "forras_tipus": "jooble",
        })
    return allasok


def szakma_gyujtes(szakma: str, kategoria: str) -> int:
    """Egy szakma teljes feldolgozása: keresés → duplikátum-szűrés →
    készség-kinyerés → mentés. Visszaadja az új hirdetések számát."""
    print(f"\n=== {szakma} ===")
    allasok = jooble_kereses(szakma)
    print(f"  Jooble talalat: {len(allasok)}")
    if not allasok:
        return 0

    # Duplikátum-szűrés MÉG a készség-kinyerés előtt (API-költség-kímélés):
    # amit már ismerünk, arra nem hívunk modellt.
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
    return mentve


def main():
    if not JOOBLE_API_KEY:
        print("HIBA: JOOBLE_API_KEY hianyzik a .env-bol!")
        return
    if kliens() is None:
        print("HIBA: a Supabase kapcsolat nincs beallitva (.env)!")
        return

    # Parancssori szakma: csak azt gyűjtjük (teszteléshez praktikus)
    if len(sys.argv) > 1:
        lista = [(sys.argv[1], "Egyéb")]
    else:
        lista = SZAKMAK

    print(f"Jooble gyujto indul — {len(lista)} szakma")
    osszes = 0
    for szakma, kategoria in lista:
        try:
            osszes += szakma_gyujtes(szakma, kategoria)
        except Exception as e:
            print(f"  VARATLAN HIBA ({szakma}): {e} — megyunk tovabb.")
        time.sleep(2)  # kíméletes tempó az API-k felé

    print(f"\nKESZ! Osszesen {osszes} uj hirdetes mentve.")


if __name__ == "__main__":
    main()
