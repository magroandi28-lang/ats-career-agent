# -*- coding: utf-8 -*-
# Céginfó Ágens - agents/ceginfo_agensek.py
# Ingyenes Google scraping + Claude összefoglalás

import requests
from bs4 import BeautifulSoup
import anthropic
import os
import json
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

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
    2. Claude összefoglalja őszintén
    """

    print(f"  Céginfó keresése: {ceg_nev}")

    # Több keresés különböző szempontból
    velemenyek_raw = google_scrape(f"{ceg_nev} munkahely vélemény dolgozó tapasztalat")
    ber_raw = google_scrape(f"{ceg_nev} fizetés bér átlagbér 2025 2026")
    fluktuacio_raw = google_scrape(f"{ceg_nev} fluktuáció munkavállaló felmondás")

    # Összegyűjtjük amit találtunk
    osszes_info = "\n".join([
        "VÉLEMÉNYEK:",
        "\n".join(velemenyek_raw[:3]),
        "\nBÉREK:",
        "\n".join(ber_raw[:2]),
        "\nFLUKTUÁCIÓ:",
        "\n".join(fluktuacio_raw[:2])
    ])

    # Claude összefoglalja őszintén
    prompt = f"""Te egy őszinte munkavállalói tanácsadó vagy.

Cég neve: {ceg_nev}

Internetes találatok a cégről:
{osszes_info}

Ha nincs elég adat → Claude saját tudásából egészítsd ki amit tudsz erről a cégről.

Adj RÖVID, ŐSZINTE összefoglalót. Válaszolj KIZÁRÓLAG JSON formátumban:

{{
  "bersav": "Konkrét összeg pl. 300.000-380.000 Ft/hó — NE írj 'piaci bérezés'-t!",
  "fluktuacio": "Magas / Közepes / Alacsony — és egy mondat miért",
  "velemenyek": "1-2 mondatos ŐSZINTE összefoglaló — ha szar hely akkor azt írd!",
  "figyelmeztetes": "Ha van komoly negatívum — null ha nincs"
}}

FONTOS:
- Legyél ŐSZINTE — ha rossz hely dolgozni, mondd ki!
- Konkrét bérek kellenek — ne általánosságok
- Ha magas a fluktuáció — írd ki egyértelműen
- Maximum 2-2 mondat minden mezőben"""

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )

    szoveg = response.content[0].text.strip()
    if "```json" in szoveg:
        szoveg = szoveg.split("```json")[1].split("```")[0].strip()
    elif "```" in szoveg:
        szoveg = szoveg.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(szoveg)
    except:
        return {
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