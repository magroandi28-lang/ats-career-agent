# -*- coding: utf-8 -*-
"""TUDÁSBÁZIS-ZAJSZŰRŐ — determinisztikus, AI nélkül, 0 Ft.

Törli a tudasanyag táblából a nem-tudás szakaszokat:
  - tartalomjegyzék (sok pontozott sor / magas pont-arány)
  - alacsony betűarány (oldalszám-, szám-, jelhalmok)
  - irodalomjegyzék-szerű szakaszok (sorok többsége évszám+oldalszám minta)

Futtatás:  python scripts/tudas_zajszuro.py          # csak MUTATJA, mit törölne
           python scripts/tudas_zajszuro.py --torol   # ténylegesen töröl
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.adatbazis import kliens  # noqa: E402


def zajos(szoveg: str) -> str:
    """Visszaadja a zaj okát, vagy üres stringet, ha a szakasz rendben van."""
    if not szoveg:
        return "ures"
    hossz = len(szoveg)

    # 1) Pont-arány (tartalomjegyzék-pontsorok: "Fejezet ...... 12")
    pontok = szoveg.count(".")
    if pontok / hossz > 0.2:
        return "tartalomjegyzek (pontsorok)"

    # 2) Betű-arány (számhalmok, táblázat-roncsok)
    betuk = sum(1 for c in szoveg if c.isalpha())
    if betuk / hossz < 0.5:
        return "alacsony betuarany"

    sorok = [s.strip() for s in szoveg.splitlines() if s.strip()]
    if not sorok:
        return "ures"

    # 3) Sorok többsége oldalszámra/évszámra végződik (TOC, irodalomjegyzék)
    szamvegu = sum(1 for s in sorok if re.search(r"(\.{3,}|\s)\d{1,4}$", s))
    if len(sorok) >= 5 and szamvegu / len(sorok) > 0.5:
        return "tartalom-/irodalomjegyzek (szamra vegzodo sorok)"

    # 4) Irodalomjegyzék: sorok többségében (évszám) hivatkozás-minta
    hivatkozas = sum(1 for s in sorok if re.search(r"\(\d{4}\)", s))
    if len(sorok) >= 5 and hivatkozas / len(sorok) > 0.6:
        return "irodalomjegyzek (hivatkozas-mintak)"

    return ""


def main():
    torol = "--torol" in sys.argv
    db = kliens()
    if db is None:
        print("HIBA: nincs Supabase kapcsolat!")
        return

    sorok, start = [], 0
    while True:
        r = (db.table("tudasanyag").select("id, forras, szoveg")
               .order("id").range(start, start + 999).execute())
        adag = r.data or []
        sorok.extend(adag)
        if len(adag) < 1000:
            break
        start += 1000
    print(f"Osszes szakasz: {len(sorok)}")

    zajosok = []
    okok = {}
    for s in sorok:
        ok = zajos(s["szoveg"])
        if ok:
            zajosok.append(s)
            okok[ok] = okok.get(ok, 0) + 1

    print(f"Zajosnak itelt: {len(zajosok)}")
    for ok, db_ in sorted(okok.items(), key=lambda x: -x[1]):
        print(f"  - {ok}: {db_} db")
    print("\nPeldak (elso 5):")
    for s in zajosok[:5]:
        print(f"  [{s['forras']}] {s['szoveg'][:80].replace(chr(10), ' ')}...")

    if not torol:
        print("\nEz csak ELONEZET volt. Torles:  python scripts/tudas_zajszuro.py --torol")
        return

    azonositok = [s["id"] for s in zajosok]
    for i in range(0, len(azonositok), 100):
        db.table("tudasanyag").delete().in_("id", azonositok[i:i + 100]).execute()
    print(f"\nKESZ: {len(azonositok)} zajos szakasz torolve. "
          f"Maradt: {len(sorok) - len(azonositok)}.")


if __name__ == "__main__":
    main()
