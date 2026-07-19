# -*- coding: utf-8 -*-
"""KSH-import — scripts/ksh_import.py

Két hivatalos KSH STADAT-táblát tölt a piaci_statisztikak táblába:
  - mun0208: bruttó átlagkereset FOGLALKOZÁSOK szerint (éves, országos)
  - mun0206: bruttó átlagkereset VÁRMEGYÉK/régiók szerint (negyedéves)

AI nélkül, tisztán letöltés + feldolgozás. Újrafuttatható (előbb törli
a korábbi KSH-sorokat, aztán berakja a frisset). Negyedévente érdemes
futtatni:  python scripts/ksh_import.py
"""

import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.adatbazis import kliens  # noqa: E402

URL_FOGLALKOZAS = "https://www.ksh.hu/stadat_files/mun/hu/mun0208.csv"
URL_MEGYE = "https://www.ksh.hu/stadat_files/mun/hu/mun0206.csv"


def letolt(url: str) -> list:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    szoveg = r.content.decode("cp1250", errors="replace")
    return [sor.split(";") for sor in szoveg.splitlines()]


def szam(cella: str):
    c = (cella or "").replace(" ", "").replace("\xa0", "").replace('"', "").strip()
    return int(c) if c.isdigit() else None


def foglalkozasok() -> list:
    sorok = letolt(URL_FOGLALKOZAS)
    fejlec = sorok[1]
    # Az utolsó "Együtt" oszlop éve (pl. "2025 Együtt")
    egyutt_idx = [i for i, f in enumerate(fejlec) if "Egy" in f][-1]
    ev = "".join(ch for ch in fejlec[egyutt_idx] if ch.isdigit())

    adatok = []
    for mezok in sorok[2:]:
        if len(mezok) <= egyutt_idx:
            continue
        feor, nev = mezok[0].strip(), mezok[1].strip()
        ertek = szam(mezok[egyutt_idx])
        if feor and nev and ertek:
            adatok.append({
                "feor_kod": feor, "megnevezes": nev, "regio": "Országos",
                "mutato": "brutto_atlagkereset", "ertek": ertek,
                "idoszak": ev, "forras": "KSH mun0208",
            })
    return adatok


def megyek() -> list:
    sorok = letolt(URL_MEGYE)
    fejlec = sorok[1]
    adatok = []
    brutto_szakasz = False
    for mezok in sorok[2:]:
        elso = (mezok[0] or "").strip()
        szint = (mezok[1] or "").strip() if len(mezok) > 1 else ""
        if elso.startswith("Bruttó"):
            brutto_szakasz = True
            continue
        if elso and not szint and not any(szam(m) for m in mezok[2:]):
            brutto_szakasz = False  # új szakasz kezdődik (pl. nettó)
            continue
        if not brutto_szakasz or not elso or not szint:
            continue
        # Az utolsó kitöltött adat-cella + a hozzá tartozó időszak-fejléc
        utolso = None
        for i in range(len(mezok) - 1, 1, -1):
            if szam(mezok[i]) is not None:
                utolso = i
                break
        if utolso is None:
            continue
        adatok.append({
            "feor_kod": "", "megnevezes": None, "regio": elso,
            "mutato": "brutto_atlagkereset", "ertek": szam(mezok[utolso]),
            "idoszak": (fejlec[utolso] or "").strip(), "forras": "KSH mun0206",
        })
    return adatok


def main():
    db = kliens()
    if db is None:
        print("HIBA: nincs Supabase kapcsolat!")
        return

    fogl = foglalkozasok()
    megy = megyek()
    print(f"Letoltve: {len(fogl)} foglalkozas + {len(megy)} teruleti sor.")

    # Idempotens: a korábbi KSH-sorokat cseréljük
    db.table("piaci_statisztikak").delete().like("forras", "KSH%").execute()

    osszes = fogl + megy
    for i in range(0, len(osszes), 400):
        db.table("piaci_statisztikak").insert(osszes[i:i + 400]).execute()

    print(f"KESZ! {len(osszes)} KSH-sor betoltve a piaci_statisztikak tablaba.")


if __name__ == "__main__":
    main()
