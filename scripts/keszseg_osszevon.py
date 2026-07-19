# -*- coding: utf-8 -*-
"""Készség-ÖSSZEVONÓ (2. menet) — scripts/keszseg_osszevon.py

A tisztító adagokban dolgozott, ezért a különböző adagokba eső
szinonimák ("angol nyelv" / "angol nyelvtudás") külön maradtak.
Ez a script az ÖSSZES kanonikus nevet EGYBEN nézi át, és a még
szétszórt változatokat egy végleges névre vonja össze (Gemini, ingyen).

Futtatás:  python scripts/keszseg_osszevon.py
"""

import json
import os
import sys

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.adatbazis import kliens, osszes_sor  # noqa: E402

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
              "gemini-2.5-flash:generateContent")


def main():
    if not GEMINI_API_KEY:
        print("HIBA: GEMINI_API_KEY hianyzik!")
        return
    db = kliens()
    if db is None:
        print("HIBA: nincs Supabase kapcsolat!")
        return

    sorok = osszes_sor("keszsegek", "id, nev, kanonikus")
    nevek = sorted({(s.get("kanonikus") or s.get("nev") or "").strip()
                    for s in sorok if (s.get("kanonikus") or s.get("nev"))})
    print(f"{len(nevek)} egyedi keszsegnev — osszevonas egyetlen menetben...")

    # Ábécé-sorrendben, átfedő darabokban — a szinonimák egymás mellett vannak,
    # így a darabolás nem választja szét őket.
    import time as _t
    DARAB, ATFEDES = 220, 25
    parok = []
    i = 0
    while i < len(nevek):
        resz = nevek[max(0, i - ATFEDES):i + DARAB]
        i += DARAB
        lista = "\n".join(f"- {n}" for n in resz)
        prompt = f"""Készségnevek listáját kapod. Keresd meg az AZONOS JELENTÉSŰ
(szinonima / írásváltozat / kötőjeles változat) neveket, és vond össze őket
EGY végleges névre. Példák: "angol nyelv" és "angol nyelvtudás" -> "angol nyelvtudás";
"full-stack fejlesztés", "fullstack fejlesztés", "full stack fejlesztés" -> "full-stack fejlesztés";
"Python fejlesztés" és "Python programozás" -> "Python fejlesztés".
NE vonj össze különböző jelentésű dolgokat (a "Python" eszköz és a "Python fejlesztés" feladat maradhat külön).

LISTA:
{lista}

Válaszolj KIZÁRÓLAG JSON-tömbként, CSAK az összevonandó elemekről:
[{{"rol": "régi név", "ra": "végleges név"}}]
Ha nincs mit összevonni, adj üres tömböt: []"""

        try:
            resp = requests.post(
                GEMINI_URL, params={"key": GEMINI_API_KEY},
                json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=180,
            )
            resp.raise_for_status()
            t = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if "```json" in t:
                t = t.split("```json")[1].split("```")[0].strip()
            elif "```" in t:
                t = t.split("```")[1].split("```")[0].strip()
            parok.extend(json.loads(t))
            print(f"  {min(i, len(nevek))}/{len(nevek)} atnezve...")
        except Exception as e:
            print(f"  Hiba ennel a darabnal: {e} — megyunk tovabb.")
        _t.sleep(6)

    print(f"{len(parok)} osszevonas javasolva.")

    frissitve = 0
    for p in parok:
        rol = (p.get("rol") or "").strip()
        ra = (p.get("ra") or "").strip()
        if not rol or not ra or rol == ra:
            continue
        db.table("keszsegek").update({"kanonikus": ra}).eq("kanonikus", rol).execute()
        db.table("keszsegek").update({"kanonikus": ra}).is_("kanonikus", "null").eq("nev", rol).execute()
        print(f"  {rol}  ->  {ra}")
        frissitve += 1

    print(f"KESZ! {frissitve} nev osszevonva.")


if __name__ == "__main__":
    main()
