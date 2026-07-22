# -*- coding: utf-8 -*-
"""FEOR-MEGFELELTETŐ — a szakmak tábla minden sorát a hivatalos KSH FEOR-08
foglalkozás-kódhoz rendeli, hogy a "rokonnév" kérdés ne találgatás legyen,
hanem tény: két szakma akkor és csak akkor ugyanaz, ha ugyanarra a FEOR-kódra
esik.

CSAK JELENTÉST ÍR — az adatbázist NEM módosítja. A kimenetet Andi nézi át,
és csak jóváhagyás után kerül vissza bármi a szakmak táblába.

Futtatás:  python scripts/feor_megfeleltetes.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.adatbazis import kliens  # noqa: E402
from utils.openai_kliens import gpt, MINOSEGI  # noqa: E402


def feor_lista():
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "db", "feor_lista.json"), encoding="utf-8") as f:
        return json.load(f)


def main():
    db = kliens()
    if db is None:
        print("HIBA: nincs Supabase kapcsolat!")
        return

    szakmak = db.table("szakmak").select("id, nev, kategoria").order("nev").execute().data or []
    feor = feor_lista()
    print(f"Szakmak a tablaban: {len(szakmak)} | FEOR-kodok: {len(feor)}")

    feor_szoveg = "\n".join(f"{e['kod']} {e['nev']}" for e in feor)
    szakma_szoveg = "\n".join(f"[{i}] {s['nev']}" for i, s in enumerate(szakmak))

    prompt = f"""Egy magyar álláskereső alkalmazás jelenlegi szakma-listáját kell
megfeleltetned a hivatalos KSH FEOR-08 foglalkozás-kódoknak.

A HIVATALOS FEOR-08 LISTA (kód + név):
{feor_szoveg}

A JELENLEGI SZAKMA-LISTA (sorszámmal):
{szakma_szoveg}

Feladat: minden sorszámozott szakmához add meg a LEGJOBBAN ILLŐ FEOR-kódot.
Ha egy szakma túl általános / nem tesztadat / nem valódi szakma (pl. egy
konkrét szenioritási szint, ami nem önálló FEOR-kategória), azt jelezd külön.

Válaszolj KIZÁRÓLAG JSON-tömbként:
[
  {{"index": 0, "szakma": "adatelemző", "feor_kod": "2513", "feor_nev": "...",
    "megjegyzes": ""}}
]
A "megjegyzes" mezőbe írd, ha gyanús (pl. "nem önálló FEOR-kategória, inkább
X szakma szenioritási szintje" vagy "duplikátum-gyanú Y szakmával")."""

    print("Megfeleltetes kereses (1 AI-hivas, gpt-5.6-terra)...")
    valasz = gpt([{"role": "user", "content": prompt}], model=MINOSEGI,
                 max_tokens=12000, reasoning_effort="low")
    if "```json" in valasz:
        valasz = valasz.split("```json")[1].split("```")[0].strip()
    elif "```" in valasz:
        valasz = valasz.split("```")[1].split("```")[0].strip()

    try:
        megfeleltetes = json.loads(valasz)
    except json.JSONDecodeError:
        print("HIBA: nem sikerult ertelmezni a valaszt:")
        print(valasz[:2000])
        return

    # Csoportositas FEOR-kod szerint -> ami egy kodra esik, az UGYANAZ
    kod_szerint = {}
    for m in megfeleltetes:
        kod = m.get("feor_kod", "?")
        kod_szerint.setdefault(kod, []).append(m)

    print(f"\n{'='*70}\nEGYEDI FEOR-KOD -> hany jelenlegi szakma esik ra\n{'='*70}")
    dupla_csoport = 0
    for kod, tagok in sorted(kod_szerint.items()):
        if len(tagok) > 1:
            dupla_csoport += 1
            nevek = [t["szakma"] for t in tagok]
            print(f"\n⚠️  {kod} ({tagok[0].get('feor_nev','')}) <- {len(tagok)} szakma UGYANARRA esik:")
            for n in nevek:
                print(f"      - {n}")

    print(f"\n{'='*70}\nTELJES LISTA megjegyzessel (ha van)\n{'='*70}")
    for m in megfeleltetes:
        if m.get("megjegyzes"):
            print(f"  {m['szakma']:35s} -> {m.get('feor_kod','?'):6s} | {m['megjegyzes']}")

    print(f"\nOSSZESITES: {len(szakmak)} szakma -> {len(kod_szerint)} egyedi FEOR-kod "
          f"({dupla_csoport} kodra esik tobb szakma is, azaz {dupla_csoport} "
          f"osszevonando csoport).")

    with open("outputs/feor_megfeleltetes.json", "w", encoding="utf-8") as f:
        json.dump(megfeleltetes, f, ensure_ascii=False, indent=1)
    print("\nReszletes eredmeny mentve: outputs/feor_megfeleltetes.json")
    print("EZ CSAK JELENTES — az adatbazisba semmi nem irodott vissza.")


if __name__ == "__main__":
    main()
