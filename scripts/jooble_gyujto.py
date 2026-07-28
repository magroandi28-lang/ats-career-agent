# -*- coding: utf-8 -*-
"""Jooble állásgyűjtő — scripts/jooble_gyujto.py

A Jooble API-ból letölti a friss hirdetéseket, kiszűri a duplikátumokat,
majd elmenti őket a Supabase-be.

Futtatás:
    python scripts/jooble_gyujto.py
    python scripts/jooble_gyujto.py "bolti eladó"
"""

import os
import re
import sys
import time

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.hirdetes_snapshot import (  # noqa: E402
    gyujtesi_futas_azonosito,
    gyujto_verzio,
    kanonikus_json,
    sha256_szoveg,
)
from utils.adatbazis import (  # noqa: E402
    gyujtes_mentese,
    keszsegnev_normalizalas,
    kliens,
)

load_dotenv()

JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY", "")
JOOBLE_URL = "https://hu.jooble.org/api/"

SZAKMAK = [
    ("bolti eladó", "Kereskedelem"),
    ("pénztáros", "Kereskedelem"),
    ("raktáros", "Kereskedelem"),
    ("szakács", "Szolgáltatás"),
    ("felszolgáló", "Szolgáltatás"),
    ("ügyfélszolgálati munkatárs", "Szolgáltatás"),
    ("adminisztratív asszisztens", "Szolgáltatás"),
    ("könyvelő", "Szolgáltatás"),
    ("villanyszerelő", "Ipar"),
    ("karbantartó", "Ipar"),
    ("gépkezelő", "Ipar"),
    ("sofőr", "Szolgáltatás"),
    ("ápoló", "Egészségügy"),
    ("egészségügyi asszisztens", "Egészségügy"),
    ("szoftvertesztelő", "IT"),
    ("Python fejlesztő", "IT"),
    ("AI mérnök", "IT"),
    ("adatelemző", "IT"),
    ("frontend fejlesztő", "IT"),
    ("rendszergazda", "IT"),
    ("DevOps mérnök", "IT"),
    ("IT projektmenedzser", "IT"),
    ("HR munkatárs", "Szolgáltatás"),
    ("marketing munkatárs", "Szolgáltatás"),
    ("pénzügyi ügyintéző", "Szolgáltatás"),
    ("logisztikai koordinátor", "Szolgáltatás"),
    ("recepciós", "Szolgáltatás"),
    ("értékesítő", "Kereskedelem"),
    ("targoncavezető", "Ipar"),
    ("hegesztő", "Ipar"),
    ("CNC gépkezelő", "Ipar"),
    ("autószerelő", "Ipar"),
    ("gyári operátor", "Ipar"),
    ("kőműves", "Építőipar"),
    ("biztonsági őr", "Szolgáltatás"),
    ("takarító", "Szolgáltatás"),
    ("futár", "Szolgáltatás"),
    ("óvodapedagógus", "Oktatás"),
    ("gépészmérnök", "Ipar"),
    ("villamosmérnök", "Ipar"),
    ("minőségbiztosítási munkatárs", "Ipar"),
    ("beszerző", "Szolgáltatás"),
    ("bérszámfejtő", "Szolgáltatás"),
    ("grafikus", "Szolgáltatás"),
    ("fodrász", "Szolgáltatás"),
    ("idősgondozó", "Egészségügy"),
    ("kertész", "Szolgáltatás"),
    ("cukrász", "Szolgáltatás"),
    ("varrómunkás", "Ipar"),
    ("festő-mázoló", "Építőipar"),
    ("orvos", "Egészségügy"),
    ("gyógyszerész", "Egészségügy"),
    ("szociális gondozó", "Egészségügy"),
    ("mentőápoló", "Egészségügy"),
    ("gyógytornász", "Egészségügy"),
    ("dietetikus", "Egészségügy"),
    ("tanár", "Oktatás"),
    ("nyelvtanár", "Oktatás"),
    ("gyógypedagógus", "Oktatás"),
    ("szociálpedagógus", "Oktatás"),
    ("jogász", "Szolgáltatás"),
    ("ügyvéd", "Szolgáltatás"),
    ("közigazgatási ügyintéző", "Szolgáltatás"),
    ("önkormányzati ügyintéző", "Szolgáltatás"),
    ("banki ügyintéző", "Szolgáltatás"),
    ("biztosítási tanácsadó", "Szolgáltatás"),
    ("kontroller", "Szolgáltatás"),
    ("adótanácsadó", "Szolgáltatás"),
    ("nemzetközi gépkocsivezető", "Szolgáltatás"),
    ("vámügyintéző", "Szolgáltatás"),
    ("szállítmányozó", "Szolgáltatás"),
    ("anyagmozgató", "Ipar"),
    ("boltvezető", "Kereskedelem"),
    ("szállodai recepciós", "Szolgáltatás"),
    ("idegenvezető", "Szolgáltatás"),
    ("lakatos", "Ipar"),
    ("asztalos", "Ipar"),
    ("víz-, gáz-, fűtésszerelő", "Építőipar"),
    ("hűtő- és klímaberendezés-szerelő", "Ipar"),
    ("esztergályos", "Ipar"),
    ("ács", "Építőipar"),
    ("tetőfedő", "Építőipar"),
    ("burkoló", "Építőipar"),
    ("mobilfejlesztő", "IT"),
    ("adatbázis-adminisztrátor", "IT"),
    ("UX/UI dizájner", "IT"),
    ("kiberbiztonsági szakértő", "IT"),
    ("data scientist", "IT"),
    ("adatmérnök", "IT"),
    ("fordító", "Szolgáltatás"),
    ("tolmács", "Szolgáltatás"),
    ("újságíró", "Szolgáltatás"),
    ("közösségimédia-menedzser", "Szolgáltatás"),
    ("minőségellenőr", "Ipar"),
    ("projektvezető", "Szolgáltatás"),
    ("key account manager", "Kereskedelem"),
    ("betanított munkás", "Ipar"),
    ("mezőgazdasági gépkezelő", "Ipar"),
    ("állattenyésztő", "Ipar"),
]

HELYSZIN = ""
MAX_OLDAL = 4
GYUJTESI_FUTAS = gyujtesi_futas_azonosito("jooble")
GYUJTO_VERZIO = gyujto_verzio("jooble")

SZINONIMAK = {
    "szoftvertesztelő": [
        "QA engineer",
        "tesztautomatizálás",
        "manuális tesztelő",
    ],
    "Python fejlesztő": [
        "Python developer",
        "backend fejlesztő",
    ],
    "AI mérnök": [
        "machine learning engineer",
        "AI fejlesztő",
        "gépi tanulás",
    ],
    "adatelemző": ["data analyst"],
    "bolti eladó": [
        "eladó-pénztáros",
        "áruházi eladó",
    ],
    "raktáros": [
        "komissiózó",
        "raktári munkatárs",
    ],
    "ügyfélszolgálati munkatárs": [
        "call center munkatárs",
    ],
    "adminisztratív asszisztens": [
        "irodai asszisztens",
    ],
    "frontend fejlesztő": [
        "React fejlesztő",
        "webfejlesztő",
    ],
    "rendszergazda": [
        "IT support",
        "helpdesk munkatárs",
    ],
    "HR munkatárs": [
        "HR asszisztens",
        "toborzó",
    ],
    "marketing munkatárs": [
        "digitális marketing",
        "social media menedzser",
    ],
    "pénzügyi ügyintéző": [
        "pénzügyi asszisztens",
    ],
    "logisztikai koordinátor": [
        "fuvarszervező",
    ],
    "értékesítő": [
        "üzletkötő",
        "sales munkatárs",
    ],
    "CNC gépkezelő": [
        "CNC forgácsoló",
    ],
    "gyári operátor": [
        "betanított munkás",
        "összeszerelő",
    ],
    "targoncavezető": [
        "targoncás raktáros",
    ],
}


def _tisztit(szoveg: str) -> str:
    """HTML-tagek és felesleges szóközök eltávolítása."""
    szoveg = re.sub(r"<[^>]+>", " ", szoveg or "")
    szoveg = (
        szoveg.replace("&nbsp;", " ")
        .replace("&amp;", "&")
    )
    return " ".join(szoveg.split())


def jooble_kereses(kulcsszo: str) -> list:
    """Állások keresése egy Jooble-kulcsszóval."""
    allasok = []

    for oldal in range(1, MAX_OLDAL + 1):
        try:
            r = requests.post(
                JOOBLE_URL + JOOBLE_API_KEY,
                json={
                    "keywords": kulcsszo,
                    "location": HELYSZIN,
                    "page": oldal,
                },
                timeout=20,
            )

            r.raise_for_status()
            jobs = r.json().get("jobs", [])

        except Exception as e:
            print(
                f"Jooble-hiba ({kulcsszo}, {oldal}. oldal): {e}"
            )
            break

        if not jobs:
            break

        for j in jobs:
            forras_adat = j if isinstance(j, dict) else {}
            cim = _tisztit(forras_adat.get("title", ""))
            raw_szoveg_ertek = forras_adat.get("snippet")
            raw_szoveg = (
                raw_szoveg_ertek
                if isinstance(raw_szoveg_ertek, str)
                else ""
            )
            link = (forras_adat.get("link") or "").strip()
            forras_azonosito = str(
                forras_adat.get("id")
                or link
                or sha256_szoveg(kanonikus_json(j))
            )
            allasok.append(
                {
                    "cim": cim,
                    "ceg": _tisztit(forras_adat.get("company", "")),
                    "snippet": _tisztit(
                        raw_szoveg
                    )[:500],
                    "link": link,
                    "helyszin": _tisztit(
                        forras_adat.get("location", "")
                    ),
                    "datum": (forras_adat.get("updated") or "")[:10],
                    "bersav": _tisztit(
                        forras_adat.get("salary", "")
                    ),
                    "forras_tipus": "jooble",
                    "_snapshot": {
                        "forras_azonosito": forras_azonosito,
                        "forras_url": link or None,
                        "keresesi_kulcsszo": kulcsszo,
                        "forras_szoveg_mezo": "snippet",
                        # Az API egyedi hirdetéseleme és eredeti snippetje
                        # változatlanul kerül az audit-rétegbe.
                        "raw_payload": j,
                        "raw_szoveg": raw_szoveg,
                        "nyelv": forras_adat.get("language"),
                        "szoveg_minoseg": "snippet",
                        "gyujto_verzio": GYUJTO_VERZIO,
                        "gyujtesi_futas": GYUJTESI_FUTAS,
                    },
                }
            )

        if len(jobs) < 15:
            break

        time.sleep(1)

    return allasok


def szakma_gyujtes(
    szakma: str,
    kategoria: str,
) -> int:
    """Egy szakma hirdetéseinek feldolgozása és mentése."""
    print(f"\n=== {szakma} ===")

    kulcsszavak = [szakma] + SZINONIMAK.get(szakma, [])
    egyedi = {}

    for kulcsszo in kulcsszavak:
        for allas in jooble_kereses(kulcsszo):
            azonosito = (
                allas["link"]
                or (allas.get("_snapshot") or {}).get(
                    "forras_azonosito"
                )
                or allas["cim"] + allas["ceg"]
            )
            egyedi.setdefault(azonosito, allas)

    allasok = list(egyedi.values())

    print(
        f"Jooble-találat: {len(allasok)} "
        f"({len(kulcsszavak)} kulcsszóval)"
    )

    if not allasok:
        return 0

    print(
        f"Snapshotolandó forráselem: {len(allasok)}"
    )

    szakma_info = {
        "szakma": szakma,
        "szakma_kategoria": kategoria,
    }

    mentve = 0

    mentve += gyujtes_mentese(szakma_info, allasok)

    return mentve


def main():
    if not JOOBLE_API_KEY:
        print("HIBA: JOOBLE_API_KEY hiányzik!")
        return

    if kliens() is None:
        print("HIBA: a Supabase-kapcsolat nincs beállítva!")
        return

    if len(sys.argv) > 1:
        lista = [
            (
                sys.argv[1],
                "Egyéb",
            )
        ]
    else:
        lista = SZAKMAK

    print(f"Jooble-gyűjtő indul — {len(lista)} szakma")

    osszes = 0

    for szakma, kategoria in lista:
        try:
            osszes += szakma_gyujtes(
                szakma,
                kategoria,
            )
        except Exception as e:
            print(
                f"Váratlan hiba ({szakma}): {e} — "
                "folytatjuk a következő szakmával."
            )

        time.sleep(2)

    keszsegnev_normalizalas()

    print(
        f"\nKÉSZ! Összesen {osszes} új hirdetés mentve."
    )


if __name__ == "__main__":
    main()
