# -*- coding: utf-8 -*-
"""TUDÁSBÁZIS-FELTÖLTŐ — 2. lépés: Gemini embedding + Supabase.

A db/tudasbazis_nyers.json szakaszait beágyazza (text-embedding-004, ingyenes)
és feltölti a 'tudasanyag' táblába. ÚJRAFUTTATHATÓ: ami már fent van, kihagyja
— ha a Gemini-kvóta elfogy (429), másnap folytatható.

Futtatás:  python scripts/tudasbazis_feltolto.py
"""

import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.adatbazis import kliens  # noqa: E402

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# EMBEDDING: OpenAI text-embedding-3-small (768 dimenzióra vágva).
# Ára: ~0,02 USD / 1M token — a teljes tudásbázis kb. 1 cent. Nincs napi kvóta.
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
EMBED_URL = "https://api.openai.com/v1/embeddings"
KOTEG = 50  # ennyi szakaszonként mentünk a Supabase-be


def embeddingek(szovegek: list) -> list:
    """Szövegek beágyazása kötegben (768 dimenzió, OpenAI)."""
    r = requests.post(
        EMBED_URL,
        headers={"Authorization": f"Bearer {OPENAI_KEY}"},
        json={"model": "text-embedding-3-small",
              "input": [s[:9000] for s in szovegek],
              "dimensions": 768}, timeout=120,
    )
    r.raise_for_status()
    adatok = sorted(r.json()["data"], key=lambda d: d["index"])
    return [d["embedding"] for d in adatok]


def main():
    db = kliens()
    if db is None or not OPENAI_KEY:
        print("HIBA: Supabase vagy OPENAI_API_KEY hianyzik!")
        return

    # --ujra kapcsoloval: mindent torol es tiszta lappal indul
    # (kell az embedding-szolgaltato VALTASAKOR — a regi vektorok nem kompatibilisek)
    if "--ujra" in sys.argv:
        print("Korabbi sorok torlese (mas vektorterbe tartoztak)...")
        db.table("tudasanyag").delete().gte("id", 0).execute()

    ut = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "db", "tudasbazis_nyers.json")
    with open(ut, encoding="utf-8") as f:
        szakaszok = json.load(f)

    # Mi van mar fent? (forras + resz paros alapjan kihagyjuk)
    fent = set()
    start = 0
    while True:
        r = (db.table("tudasanyag").select("forras, resz")
               .range(start, start + 999).execute())
        adag = r.data or []
        fent.update((s["forras"], s["resz"]) for s in adag)
        if len(adag) < 1000:
            break
        start += 1000

    varakozo = [s for s in szakaszok if (s["forras"], s["resz"]) not in fent]
    print(f"Osszes: {len(szakaszok)} | Mar fent: {len(fent)} | Feltoltendo: {len(varakozo)}")

    for i in range(0, len(varakozo), KOTEG):
        koteg = varakozo[i:i + KOTEG]
        try:
            vektorok = embeddingek([s["szoveg"] for s in koteg])
        except RuntimeError as e:
            print(f"\n{e}")
            return
        sorok = [{"forras": s["forras"], "resz": s["resz"], "szoveg": s["szoveg"],
                  "embedding": v} for s, v in zip(koteg, vektorok)]
        db.table("tudasanyag").insert(sorok).execute()
        print(f"  Feltoltve: {min(i + KOTEG, len(varakozo))}/{len(varakozo)}")
        time.sleep(1)  # kimeljuk a kvotat

    print("\nKESZ! A tudasbazis feltoltve.")


if __name__ == "__main__":
    main()
