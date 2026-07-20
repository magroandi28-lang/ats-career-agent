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

import json
import os
import re
import sys
import time

import requests
from dotenv import load_dotenv

# A projekt gyökerét a path-ra tesszük, hogy az agents/utils importok működjenek
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

# A készség-kinyerést a Google Gemini INGYENES szintje végzi — 0 Ft.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODELL = "gemini-2.5-flash"
GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
              f"{GEMINI_MODELL}:generateContent")

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
    ("egészségügyi asszisztens", "Egészségügy"),
    # IT
    ("szoftvertesztelő", "IT"),
    ("Python fejlesztő", "IT"),
    ("AI mérnök", "IT"),
    ("adatelemző", "IT"),
    ("frontend fejlesztő", "IT"),
    ("rendszergazda", "IT"),
    ("DevOps mérnök", "IT"),
    ("IT projektmenedzser", "IT"),
    # Iroda, gazdaság
    ("HR munkatárs", "Szolgáltatás"),
    ("marketing munkatárs", "Szolgáltatás"),
    ("pénzügyi ügyintéző", "Szolgáltatás"),
    ("logisztikai koordinátor", "Szolgáltatás"),
    ("recepciós", "Szolgáltatás"),
    ("értékesítő", "Kereskedelem"),
    # Ipar, építőipar, fizikai
    ("targoncavezető", "Ipar"),
    ("hegesztő", "Ipar"),
    ("CNC gépkezelő", "Ipar"),
    ("autószerelő", "Ipar"),
    ("gyári operátor", "Ipar"),
    ("kőműves", "Építőipar"),
    # Szolgáltatás, egyéb
    ("biztonsági őr", "Szolgáltatás"),
    ("takarító", "Szolgáltatás"),
    ("futár", "Szolgáltatás"),
    ("óvodapedagógus", "Oktatás"),
    # További bővítés — cél a széles lefedettség
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
]

HELYSZIN = ""                    # üres = egész Magyarország (lehet pl. "Budapest")
MAX_OLDAL = 4                    # ennyi oldalt lapozunk kulcsszavanként (~20 hirdetés/oldal)
CSOMAG_MERET = 10                # ennyit adunk egyszerre a készség-kinyerőnek

# Szinonimák: ugyanazt a szakmát több kulcsszóval is keressük,
# így szélesebb a merítés (a duplikátumokat a rendszer kiszűri).
SZINONIMAK = {
    "szoftvertesztelő": ["QA engineer", "tesztautomatizálás", "manuális tesztelő"],
    "Python fejlesztő": ["Python developer", "backend fejlesztő"],
    "AI mérnök": ["machine learning engineer", "AI fejlesztő", "gépi tanulás"],
    "adatelemző": ["data analyst"],
    "bolti eladó": ["eladó-pénztáros", "áruházi eladó"],
    "raktáros": ["komissiózó", "raktári munkatárs"],
    "ügyfélszolgálati munkatárs": ["call center munkatárs"],
    "adminisztratív asszisztens": ["irodai asszisztens"],
    "frontend fejlesztő": ["React fejlesztő", "webfejlesztő"],
    "rendszergazda": ["IT support", "helpdesk munkatárs"],
    "HR munkatárs": ["HR asszisztens", "toborzó"],
    "marketing munkatárs": ["digitális marketing", "social media menedzser"],
    "pénzügyi ügyintéző": ["pénzügyi asszisztens"],
    "logisztikai koordinátor": ["fuvarszervező"],
    "értékesítő": ["üzletkötő", "sales munkatárs"],
    "CNC gépkezelő": ["CNC forgácsoló"],
    "gyári operátor": ["betanított munkás", "összeszerelő"],
    "targoncavezető": ["targoncás raktáros"],
}


def keszsegek_kinyerese(allasok: list) -> list:
    """Készség-kinyerés a Google Gemini INGYENES API-jával (nem Claude!).
    Visszatérés: listák listája, az allasok sorrendjében."""
    if not allasok:
        return []
    if not GEMINI_API_KEY:
        print("  FIGYELEM: GEMINI_API_KEY hianyzik — keszsegek nelkul mentunk.")
        return [[] for _ in allasok]

    lista = "\n\n".join([
        f"[{i}] {a.get('cim','')} — {a.get('ceg','')}\n{a.get('snippet','')}"
        for i, a in enumerate(allasok)
    ])

    prompt = f"""Álláshirdetésekből kell strukturáltan kinyerned a készségeket és elvárásokat.

HIRDETÉSEK (sorszámmal):
{lista}

Minden hirdetéshez add meg a benne szereplő készségeket SZAKMAI néven:
- tipus lehet (PONTOSAN így válaszd szét!):
  "elvaras" = amit a jelölttől MEGKÖVETELNEK: végzettség, tapasztalat, nyelvtudás, bizonyítvány, jogosítvány
  "feladat" = amit a munkakörben CSINÁLNI kell: tevékenység (pl. tesztek írása, árufeltöltés)
  "eszkoz" = konkrét szoftver, technológia vagy gép NEVE (Python, SAP, targonca)
  "soft" = személyes készség (csapatmunka, precizitás)
  "iparag" = terület/szektor, ami NEM készség (autóipar, fintech, egészségügy)
- A pongyola megfogalmazást fordítsd szakmaira (pl. "kassza" → "pénztárgép kezelése").
- Ugyanazt a fogalmat MINDIG ugyanazzal a névvel add vissza (egységes elnevezés).
- A nevet kisbetűvel írd, KIVÉVE a rövidítéseket és tulajdonneveket (HACCP, SQL, Python).
- Hirdetésenként 3-8 elem. Helyszínt, bért, munkaidőt, juttatást NE adj meg készségként.

Válaszolj KIZÁRÓLAG JSON-tömbként, minden más szöveg nélkül:
[
  {{"index": 0, "keszsegek": [{{"nev": "pénztárgép kezelése", "tipus": "feladat"}}]}}
]"""

    try:
        r = requests.post(
            GEMINI_URL,
            params={"key": GEMINI_API_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=60,
        )
        r.raise_for_status()
        t = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
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
        print(f"  Gemini hiba (keszseg-kinyeres): {e}")
        return [[] for _ in allasok]


def _tisztit(szoveg: str) -> str:
    """HTML-tagek és felesleges szóközök eltávolítása a Jooble mezőkből."""
    szoveg = re.sub(r"<[^>]+>", " ", szoveg or "")
    szoveg = szoveg.replace("&nbsp;", " ").replace("&amp;", "&")
    return " ".join(szoveg.split())


def jooble_kereses(kulcsszo: str) -> list:
    """Egy kulcsszó friss hirdetései a Jooble API-ból — LAPOZÁSSAL:
    a 'page' paraméterrel több oldalt kérünk le (oldalanként ~20 hirdetés)."""
    allasok = []
    for oldal in range(1, MAX_OLDAL + 1):
        try:
            r = requests.post(
                JOOBLE_URL + JOOBLE_API_KEY,
                json={"keywords": kulcsszo, "location": HELYSZIN, "page": oldal},
                timeout=20,
            )
            r.raise_for_status()
            jobs = r.json().get("jobs", [])
        except Exception as e:
            print(f"  Jooble hiba ({kulcsszo}, {oldal}. oldal): {e}")
            break

        if not jobs:
            break

        for j in jobs:
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

        if len(jobs) < 15:  # ennél kevesebb találat = ez volt az utolsó oldal
            break
        time.sleep(1)
    return allasok


def szakma_gyujtes(szakma: str, kategoria: str) -> int:
    """Egy szakma teljes feldolgozása: keresés → duplikátum-szűrés →
    készség-kinyerés → mentés. Visszaadja az új hirdetések számát."""
    print(f"\n=== {szakma} ===")
    # A szakma neve + a szinonimái — minden kulcsszóra keresünk,
    # az átfedéseket link alapján helyben kiszűrjük.
    kulcsszavak = [szakma] + SZINONIMAK.get(szakma, [])
    egyedi = {}
    for k in kulcsszavak:
        for a in jooble_kereses(k):
            azonosito = a["link"] or (a["cim"] + a["ceg"])
            egyedi.setdefault(azonosito, a)
    allasok = list(egyedi.values())
    print(f"  Jooble talalat: {len(allasok)} ({len(kulcsszavak)} kulcsszoval)")
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
        time.sleep(5)  # a Gemini ingyenes szint perc-limitje miatt
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

    # Automatikus névegyesítés minden gyűjtés végén — nincs több kézi tisztítás
    keszsegnev_normalizalas()

    print(f"\nKESZ! Osszesen {osszes} uj hirdetes mentve.")


if __name__ == "__main__":
    main()
