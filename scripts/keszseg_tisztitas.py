# -*- coding: utf-8 -*-
"""Készség-tisztító — scripts/keszseg_tisztitas.py

A keszsegek tábla szinonimáit egységesíti (kanonikus név) és a rossz
típusokat javítja (pl. "autóipari ismeretek" -> iparag) a Gemini
INGYENES API-jával. Bármikor újrafuttatható (pl. nagyobb gyűjtés után).

Futtatás a projekt gyökeréből:
    python scripts/keszseg_tisztitas.py
"""

import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.adatbazis import kliens, osszes_sor  # noqa: E402

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
              "gemini-2.5-flash:generateContent")

CSOMAG = 80  # ennyi készséget adunk egy Gemini-hívásba


def gemini_tisztit(sorok: list) -> list:
    lista = "\n".join([f'{s["id"]} | {s["nev"]} | {s["tipus"]}' for s in sorok])
    prompt = f"""Álláshirdetésekből kinyert készséglistát tisztítunk.

LISTA (id | név | jelenlegi típus):
{lista}

Feladatod MINDEN sorra:
1) "kanonikus": egységes, szakmai név. A szinonimák és írásváltozatok UGYANAZT a
   kanonikus nevet kapják (pl. "szoftver tesztelés" és "szoftvertesztelés" ->
   "szoftvertesztelés"; "kassza kezelése" -> "pénztárgép kezelése").
   Kisbetűs, kivéve rövidítések/tulajdonnevek (SQL, Python, HACCP).
2) "tipus" javítása, lehetséges értékek:
   - "eszkoz": szoftver, gép, technológia (Python, SQL, targonca)
   - "feladat": munkakörben végzett tevékenység (tesztautomatizálás, árufeltöltés)
   - "elvaras": elvárt tudás/végzettség/tapasztalat
   - "soft": személyes készség (csapatmunka, kommunikáció)
   - "iparag": terület/iparág, NEM készség (autóipari ismeretek, fintech)

Válaszolj KIZÁRÓLAG JSON-tömbként, minden id-re pontosan egy elem:
[{{"id": 1, "kanonikus": "...", "tipus": "..."}}]"""

    r = requests.post(
        GEMINI_URL, params={"key": GEMINI_API_KEY},
        json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=90,
    )
    r.raise_for_status()
    t = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    if "```json" in t:
        t = t.split("```json")[1].split("```")[0].strip()
    elif "```" in t:
        t = t.split("```")[1].split("```")[0].strip()
    return json.loads(t)


def main():
    if not GEMINI_API_KEY:
        print("HIBA: GEMINI_API_KEY hianyzik a .env-bol!")
        return
    db = kliens()
    if db is None:
        print("HIBA: Supabase kapcsolat nincs beallitva!")
        return

    minden = osszes_sor("keszsegek", "id, nev, tipus, kanonikus")
    # Csak azokat dolgozzuk fel, amiknek MÉG NINCS kanonikus neve
    sorok = [s for s in minden if not s.get("kanonikus")]
    print(f"Osszesen {len(minden)} keszseg, ebbol tisztitando: {len(sorok)}.")

    ervenyes = ("elvaras", "feladat", "eszkoz", "soft", "iparag")
    javitott = 0

    for i in range(0, len(sorok), CSOMAG):
        csomag = sorok[i:i + CSOMAG]
        try:
            valasz = gemini_tisztit(csomag)
        except Exception as e:
            if "429" in str(e):
                print(f"  Kvota-limit ({i}) — varunk 60 mp-et, aztan ujraprobaljuk...")
                time.sleep(60)
                try:
                    valasz = gemini_tisztit(csomag)
                except Exception as e2:
                    print(f"  Megint limit: {e2} — a maradek MA mar nem megy, "
                          f"futtasd ujra HOLNAP, onnan folytatja.")
                    break
            else:
                print(f"  Gemini hiba ({i}-{i+len(csomag)}): {e} — kihagyva.")
                continue

        nev_szerint = {s["id"]: s for s in csomag}
        frissitendo = []
        for v in valasz:
            vid = v.get("id")
            if vid not in nev_szerint:
                continue
            kanonikus = " ".join((v.get("kanonikus") or "").split())
            tipus = v.get("tipus", "")
            if not kanonikus or tipus not in ervenyes:
                continue
            frissitendo.append({
                "id": vid,
                "nev": nev_szerint[vid]["nev"],
                "kanonikus": kanonikus,
                "tipus": tipus,
            })

        for f in frissitendo:
            try:
                db.table("keszsegek").update(
                    {"kanonikus": f["kanonikus"], "tipus": f["tipus"]}
                ).eq("id", f["id"]).execute()
                javitott += 1
            except Exception as e:
                print(f"  Frissites hiba (id={f['id']}): {e}")
        print(f"  {i + len(csomag)}/{len(sorok)} feldolgozva...")

        time.sleep(12)  # Gemini ingyenes perc-limit (lassabb, de nem akad el)

    print(f"KESZ! {javitott} keszseg tisztitva/egysegesitve.")


if __name__ == "__main__":
    main()
