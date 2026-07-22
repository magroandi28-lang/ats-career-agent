# -*- coding: utf-8 -*-
# Céginfó Ágens - agents/ceginfo_agensek.py
# Ingyenes Google scraping + OpenAI összefoglalás

import requests
from bs4 import BeautifulSoup
import os
import sys
import json
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.openai_kliens import gpt, GYORS  # noqa: E402

load_dotenv()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "hu-HU,hu;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def google_scrape(query: str, max_results: int = 5) -> list:
    """Google keresés scraping-gel — ingyenes"""
    try:
        url = f"https://www.google.com/search?q={requests.utils.quote(query)}&hl=hu&gl=hu&num={max_results}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        snippetek = []

        # Google snippetek kiszedése
        for div in soup.find_all("div", class_=["BNeawe", "VwiC3b", "s3v9rd"]):
            szoveg = div.get_text(strip=True)
            if szoveg and len(szoveg) > 30:
                snippetek.append(szoveg)

        # Alternatív selector
        if not snippetek:
            for span in soup.find_all("span", class_=["aCOpRe", "st"]):
                szoveg = span.get_text(strip=True)
                if szoveg and len(szoveg) > 30:
                    snippetek.append(szoveg)

        return snippetek[:max_results]

    except Exception as e:
        print(f"Google scraping hiba: {e}")
        return []


def ceginfo_kereses(ceg_nev: str) -> dict:
    """
    Valódi céginfót keres ingyenesen:
    1. Google scraping — vélemények, bérek, hírek
    2. OpenAI (gpt-5.6-luna) összefoglalja őszintén
    """

    print(f"  Céginfó keresése: {ceg_nev}")

    # Több keresés különböző szempontból
    profil_raw = google_scrape(f"{ceg_nev} cég profil tevékenység mivel foglalkozik")
    velemenyek_raw = google_scrape(f"{ceg_nev} munkahely vélemény dolgozó tapasztalat")
    ber_raw = google_scrape(f"{ceg_nev} fizetés bér átlagbér 2025 2026")
    fluktuacio_raw = google_scrape(f"{ceg_nev} fluktuáció munkavállaló felmondás")

    # Összegyűjtjük amit találtunk
    osszes_info = "\n".join([
        "CÉGPROFIL:",
        "\n".join(profil_raw[:3]),
        "\nVÉLEMÉNYEK:",
        "\n".join(velemenyek_raw[:3]),
        "\nBÉREK:",
        "\n".join(ber_raw[:2]),
        "\nFLUKTUÁCIÓ:",
        "\n".join(fluktuacio_raw[:2])
    ])

    # OpenAI összefoglalja őszintén
    prompt = f"""Te egy őszinte munkavállalói tanácsadó vagy.

Cég neve: {ceg_nev}

Internetes találatok a cégről:
{osszes_info}

SZIGORÚ SZABÁLY — CSAK MEGERŐSÍTETT ADAT:
- KIZÁRÓLAG a fenti internetes találatokból dolgozz, plusz abból, amit KONKRÉTAN erről a cégről biztosan tudsz.
- TILOS bérszámot kitalálni vagy "tipikus/iparági" bérsávot írni! Ha a találatokban nincs konkrét bér erről a cégről, a bersav mező legyen PONTOSAN: "Nincs megerősített béradat".
- Fluktuáció: ha nincs valódi adat, írd: "Nincs megerősített adat". Iparági általánosítás TILOS.
- A pozíció szintjét nem ismered — pozíciófüggő találgatás is TILOS.

Válaszolj KIZÁRÓLAG JSON formátumban:

{{
  "leiras": "1-2 mondat: mivel foglalkozik a cég, milyen iparágban — csak a CÉGPROFIL találatokból; ha nincs találat: 'Nincs megerősített céginfó.'",
  "meret": "Kicsi / Közepes / Nagy — csak ha a találatokból kiderül (pl. létszám, több telephely); ha nincs adat: 'Ismeretlen'",
  "bersav": "csak a találatokból; ha nincs: 'Nincs megerősített béradat'",
  "fluktuacio": "Magas / Közepes / Alacsony + 1 mondat — csak valódi adat alapján; ha nincs: 'Nincs megerősített adat'",
  "velemenyek": "1-2 mondat ŐSZINTÉN, a TALÁLATOK alapján; ha nincs találat: 'Nincs elérhető vélemény erről a cégről.'",
  "figyelmeztetes": "csak a találatokból kiderülő KONKRÉT negatívum — null ha nincs"
}}

FONTOS:
- Legyél ŐSZINTE — ha a találatok szerint rossz hely, mondd ki!
- De SOHA ne találj ki számot, és ne írj általános iparági tippet.
- Maximum 2-2 mondat minden mezőben"""

    szoveg = gpt([{"role": "user", "content": prompt}],
                 model=GYORS, max_tokens=400, reasoning_effort="low")
    if "```json" in szoveg:
        szoveg = szoveg.split("```json")[1].split("```")[0].strip()
    elif "```" in szoveg:
        szoveg = szoveg.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(szoveg)
    except:
        return {
            "leiras": "Nem sikerült lekérdezni",
            "meret": "Ismeretlen",
            "bersav": "Nem sikerült lekérdezni",
            "fluktuacio": "Ismeretlen",
            "velemenyek": "Nincs elérhető vélemény",
            "figyelmeztetes": None
        }


def ceginfok_batch(cegek: list) -> dict:
    """Több cégről egyszerre kér infót"""
    eredmenyek = {}
    for ceg in cegek:
        eredmenyek[ceg] = ceginfo_kereses(ceg)
    return eredmenyek