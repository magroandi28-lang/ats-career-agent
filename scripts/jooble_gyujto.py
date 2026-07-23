# -*- coding: utf-8 -*-
"""Jooble állásgyűjtő — scripts/jooble_gyujto.py

A Jooble API-ból letölti a friss hirdetéseket, kiszűri a duplikátumokat,
majd elmenti őket a Supabase-be.

Futtatás:
    python scripts/jooble_gyujto.py
    python scripts/jooble_gyujto.py "bolti eladó"
"""

import json
import os
import re
import sys
import time

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.adatbazis import (  # noqa: E402
    gyujtes_mentese,
    keszsegnev_normalizalas,
    kliens,
    letezo_linkek,
)

load_dotenv()

JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY", "")
JOOBLE_URL = "https://hu.jooble.org/api/"

# A napi gyűjtésnél kikapcsolható a Gemini használata.
# Így először az ingyenes szótáras címkéző dolgozhat.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODELL = os.getenv("GEMINI_MODELL", "gemini-2.5-flash")
GEMINI_KINYERES_GYUJTESKOR = os.getenv(
    "GEMINI_KINYERES_GYUJTESKOR", "1"
).strip().lower() not in ("0", "false", "nem", "off")

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODELL}:generateContent"
)

_GEMINI_KVOTA_ELFOGYOTT = False

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
CSOMAG_MERET = 10

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


def gemini_kvota_elfogyott() -> bool:
    """Jelzi, ha ebben a futásban 429-es kvótahiba érkezett."""
    return _GEMINI_KVOTA_ELFOGYOTT


def keszsegek_kinyerese(
    allasok: list,
    kenyszerit: bool = False,
) -> list:
    """Készségek kinyerése a Gemini API-val."""
    global _GEMINI_KVOTA_ELFOGYOTT

    if not allasok:
        return []

    if not kenyszerit and not GEMINI_KINYERES_GYUJTESKOR:
        return [[] for _ in allasok]

    if _GEMINI_KVOTA_ELFOGYOTT:
        return [[] for _ in allasok]

    if not GEMINI_API_KEY:
        print(
            "FIGYELEM: GEMINI_API_KEY hiányzik — "
            "készségek nélkül mentünk."
        )
        return [[] for _ in allasok]

    lista = "\n\n".join(
        [
            (
                f"[{i}] {a.get('cim', '')} — {a.get('ceg', '')}\n"
                f"{a.get('snippet', '')}"
            )
            for i, a in enumerate(allasok)
        ]
    )

    prompt = f"""
Álláshirdetésekből kell strukturáltan kinyerned a készségeket és elvárásokat.

HIRDETÉSEK:
{lista}

Minden hirdetéshez add meg a benne szereplő készségeket szakmai néven.

A típus pontosan ezek egyike lehet:
- elvaras: végzettség, tapasztalat, nyelvtudás, bizonyítvány, jogosítvány
- feladat: amit a munkakörben csinálni kell
- eszkoz: konkrét szoftver, technológia vagy gép
- soft: személyes készség
- iparag: terület vagy szektor

Szabályok:
- Hirdetésenként 3–8 elem.
- Helyszínt, bért, munkaidőt és juttatást ne adj meg készségként.
- A neveket egységes, szakmai formában add vissza.
- Válaszolj kizárólag JSON-tömbként.

Formátum:
[
  {{
    "index": 0,
    "keszsegek": [
      {{
        "nev": "pénztárgép kezelése",
        "tipus": "feladat"
      }}
    ]
  }}
]
"""

    try:
        r = requests.post(
            GEMINI_URL,
            params={"key": GEMINI_API_KEY},
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt,
                            }
                        ]
                    }
                ]
            },
            timeout=60,
        )

        if r.status_code == 429:
            _GEMINI_KVOTA_ELFOGYOTT = True
            print(
                "Gemini-kvóta elfogyott (429) — "
                "a feldolgozás leáll."
            )
            return [[] for _ in allasok]

        r.raise_for_status()

        t = (
            r.json()["candidates"][0]["content"]["parts"][0]["text"]
            .strip()
        )

        if "```json" in t:
            t = t.split("```json")[1].split("```")[0].strip()
        elif "```" in t:
            t = t.split("```")[1].split("```")[0].strip()

        adat = json.loads(t)
        eredmeny = [[] for _ in allasok]

        for elem in adat:
            idx = elem.get("index")
            if isinstance(idx, int) and 0 <= idx < len(allasok):
                eredmeny[idx] = elem.get("keszsegek", [])

        return eredmeny

    except Exception as e:
        print(f"Gemini-hiba a készségkinyerésnél: {e}")
        return [[] for _ in allasok]


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
            cim = _tisztit(j.get("title", ""))

            if not cim:
                continue

            allasok.append(
                {
                    "cim": cim,
                    "ceg": _tisztit(j.get("company", "")),
                    "snippet": _tisztit(
                        j.get("snippet", "")
                    )[:500],
                    "link": (j.get("link") or "").strip(),
                    "helyszin": _tisztit(
                        j.get("location", "")
                    ),
                    "datum": (j.get("updated") or "")[:10],
                    "bersav": _tisztit(
                        j.get("salary", "")
                    ),
                    "forras_tipus": "jooble",
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

    megvan = letezo_linkek(
        [allas["link"] for allas in allasok]
    )

    ujak = [
        allas
        for allas in allasok
        if allas["link"] not in megvan
    ]

    print(
        f"Ebből új, még nincs az adatbázisban: {len(ujak)}"
    )

    if not ujak:
        return 0

    szakma_info = {
        "szakma": szakma,
        "szakma_kategoria": kategoria,
    }

    mentve = 0

    for i in range(0, len(ujak), CSOMAG_MERET):
        csomag = ujak[i : i + CSOMAG_MERET]
        keszsegek = keszsegek_kinyerese(csomag)

        mentve += gyujtes_mentese(
            szakma_info,
            csomag,
            keszsegek,
        )

        if GEMINI_KINYERES_GYUJTESKOR:
            time.sleep(5)

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
