# -*- coding: utf-8 -*-
"""CÉGNÉV-ÖSSZEVONÓ — 'Magyar Posta Zrt.' / 'Magyar Posta ZRt.' → egy cég.

Normalizált név (kisbetű, cégforma-rövidítés nélkül) alapján csoportosít,
a hirdetéseket a legtöbb hirdetéssel bíró változat alá köti át, a többi
sort törli. AI nélkül, determinisztikus.

Futtatás:  python scripts/ceg_osszevono.py          # előnézet
           python scripts/ceg_osszevono.py --torol   # tényleges összevonás
"""

import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.adatbazis import kliens  # noqa: E402


def normal(nev: str) -> str:
    n = (nev or "").lower()
    n = re.sub(r"\b(kft|zrt|nyrt|bt|ltd|gmbh|inc|co)\.?\b", "", n)
    return re.sub(r"[\s.,]+", " ", n).strip()


def main():
    torol = "--torol" in sys.argv
    db = kliens()
    if db is None:
        print("HIBA: nincs Supabase kapcsolat!")
        return

    cegek = db.table("cegek").select("id, nev").execute().data or []
    hird = []
    start = 0
    while True:
        r = (db.table("hirdetesek").select("id, ceg_id")
               .range(start, start + 999).execute())
        adag = r.data or []
        hird.extend(adag)
        if len(adag) < 1000:
            break
        start += 1000
    darab = defaultdict(int)
    for h in hird:
        if h.get("ceg_id"):
            darab[h["ceg_id"]] += 1

    csop = defaultdict(list)
    for c in cegek:
        kulcs = normal(c["nev"])
        if kulcs:
            csop[kulcs].append(c)

    duplak = {k: v for k, v in csop.items() if len(v) > 1}
    print(f"Cegek: {len(cegek)} | Osszevonando csoport: {len(duplak)}")
    for k, v in list(duplak.items())[:10]:
        v_r = sorted(v, key=lambda c: -darab[c["id"]])
        print(f"  MARAD: '{v_r[0]['nev']}' ({darab[v_r[0]['id']]} hird.) <- " +
              ", ".join(f"'{c['nev']}' ({darab[c['id']]})" for c in v_r[1:]))

    if not torol:
        print("\nEz csak ELONEZET volt. Osszevonas: python scripts/ceg_osszevono.py --torol")
        return

    atkotott, torolt = 0, 0
    for v in duplak.values():
        v_r = sorted(v, key=lambda c: -darab[c["id"]])
        marad = v_r[0]
        for masik in v_r[1:]:
            r = (db.table("hirdetesek").update({"ceg_id": marad["id"]})
                   .eq("ceg_id", masik["id"]).execute())
            atkotott += len(r.data or [])
            db.table("cegek").delete().eq("id", masik["id"]).execute()
            torolt += 1
    print(f"\nKESZ: {atkotott} hirdetes atkotve, {torolt} duplikalt ceg torolve.")


if __name__ == "__main__":
    main()
