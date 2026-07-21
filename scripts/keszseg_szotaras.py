# -*- coding: utf-8 -*-
"""SZÓTÁR-ALAPÚ KÉSZSÉG-CÍMKÉZŐ — AI NÉLKÜL, 0 Ft, korlátlan.

A már adatbázisban lévő készségneveket (nev + kanonikus) keresi meg a
címkétlen hirdetések szövegében (határolt, kisbetű-érzéketlen illesztés).
Újrafuttatható. Amit a szótár nem talál, azt a hajnali Gemini-pótló finomítja.

Futtatás:  python scripts/keszseg_szotaras.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.adatbazis import kliens  # noqa: E402


def lapozva(db, tabla, mezok, rendez="id"):
    sorok, start = [], 0
    while True:
        r = (db.table(tabla).select(mezok).order(rendez)
               .range(start, start + 999).execute())
        adag = r.data or []
        sorok.extend(adag)
        if len(adag) < 1000:
            break
        start += 1000
    return sorok


def main():
    db = kliens()
    if db is None:
        print("HIBA: nincs Supabase kapcsolat!")
        return

    # Szótár a meglévő készségekből (3+ karakteres nevek) —
    # EGYETLEN összevont mintával, hogy gyors legyen (hosszabb nevek előre!)
    keszsegek = lapozva(db, "keszsegek", "id, nev")
    nev_id = {}
    for k in keszsegek:
        nev = (k["nev"] or "").strip().lower()
        if len(nev) >= 3 and nev not in nev_id:
            nev_id[nev] = k["id"]
    nevek_sorban = sorted(nev_id, key=len, reverse=True)
    nagy_minta = re.compile(
        r"(?<!\w)(" + "|".join(re.escape(n) for n in nevek_sorban) + r")(?!\w)")
    print(f"Szotar: {len(nev_id)} keszsegnev")

    # Címkétlen hirdetések
    hirdetesek = lapozva(db, "hirdetesek", "id, cim, snippet")
    cimkezett = {s["hirdetes_id"] for s in
                 lapozva(db, "hirdetes_keszseg", "hirdetes_id", "hirdetes_id")}
    varakozok = [h for h in hirdetesek if h["id"] not in cimkezett]
    print(f"Cimketlen hirdetes: {len(varakozok)}")

    talalt_osszes, linkek = 0, []
    for h in varakozok:
        szoveg = f"{h.get('cim') or ''} {h.get('snippet') or ''}".lower()
        nevtalalat = set(nagy_minta.findall(szoveg))
        talalatok = [nev_id[n] for n in list(nevtalalat)[:12]]
        if talalatok:
            talalt_osszes += 1
            linkek.extend({"hirdetes_id": h["id"], "keszseg_id": kid}
                          for kid in talalatok)

    for i in range(0, len(linkek), 400):
        db.table("hirdetes_keszseg").insert(linkek[i:i + 400]).execute()

    print(f"KESZ: {talalt_osszes} hirdeteshez {len(linkek)} cimke a szotarbol. "
          f"({len(varakozok) - talalt_osszes} hirdetesben nem volt ismert keszseg "
          f"— azokat a hajnali Gemini-potlo dolgozza fel.)")


if __name__ == "__main__":
    main()
