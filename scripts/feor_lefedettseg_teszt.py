# -*- coding: utf-8 -*-
"""FEOR-LEFEDETTSÉG TESZT — scripts/feor_lefedettseg_teszt.py

A 485 hivatalos FEOR-08 kategóriából megnézi, melyikre van VALÓS, AKTÍV
magyarországi hirdetés (élő EURES-lekérdezés, ingyenes, kulcs nélkül) —
azok közül, amikre a szakmak tábla MÉG NEM gyűjt.

CSAK OLVAS és egy JSON-eredményfájlba ír — a szakmak táblát NEM módosítja.
Andi ez alapján dönti el, mit vegyünk fel ténylegesen gyűjtött szakmának.

Ellenállóképes: megszakítható és újraindítható — a már letesztelt FEOR-
kódokat kihagyja (outputs/feor_lefedettseg.json-ből olvassa vissza).

Futtatás a projekt gyökeréből:
    python scripts/feor_lefedettseg_teszt.py            # a hátralévők (max 250)
    python scripts/feor_lefedettseg_teszt.py 100         # csak 100 hátralévő
"""

import concurrent.futures
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.adatbazis import kliens  # noqa: E402
from utils.eures import eures_kereses  # noqa: E402

EREDMENY_FAJL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "outputs", "feor_lefedettseg.json")
PARHUZAMOS = 8       # egyszerre ennyi EURES-kérés (udvarias tempó a publikus vegponttal)
ALAP_LIMIT = 250      # egy futtatás ennyi kódot dolgoz fel legfeljebb


def eredmeny_betoltes() -> dict:
    if os.path.exists(EREDMENY_FAJL):
        with open(EREDMENY_FAJL, encoding="utf-8") as f:
            return json.load(f)
    return {}


def eredmeny_mentes(adat: dict):
    os.makedirs(os.path.dirname(EREDMENY_FAJL), exist_ok=True)
    with open(EREDMENY_FAJL, "w", encoding="utf-8") as f:
        json.dump(adat, f, ensure_ascii=False, indent=1)


def teszt_egy(kod_nev):
    kod, nev = kod_nev
    r = eures_kereses(nev, ["hu"], darab=5)
    return kod, (r.get("talalatok", 0) if r.get("ok") else -1)


def main():
    db = kliens()
    if db is None:
        print("HIBA: nincs Supabase kapcsolat!")
        return

    szakmak = db.table("szakmak").select("feor_kod").execute().data or []
    lefedve = {s["feor_kod"] for s in szakmak if s.get("feor_kod")}
    feor = db.table("feor_lista").select("kod, nev").order("kod").execute().data or []
    print(f"FEOR osszesen: {len(feor)} | mar aktivan gyujtott: {len(lefedve)}")

    eredmeny = eredmeny_betoltes()
    hatralevo = [(e["kod"], e["nev"]) for e in feor
                 if e["kod"] not in lefedve and e["kod"] not in eredmeny]
    print(f"Meg leteszteletlen: {len(hatralevo)}")

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else ALAP_LIMIT
    csomag = hatralevo[:limit]
    if not csomag:
        print("Nincs tobb leteszteletlen kod — kesz!")
        return

    print(f"Tesztelem: {len(csomag)} kod ({PARHUZAMOS} parhuzamos kerdessel)...")
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=PARHUZAMOS) as ex:
        for kod, talalat in ex.map(teszt_egy, csomag):
            eredmeny[kod] = talalat

    eredmeny_mentes(eredmeny)
    print(f"KESZ ({time.time()-start:.0f} mp). Osszesen leteszteltve eddig: {len(eredmeny)}"
          f" / {len(feor) - len(lefedve)} hatralevo.")
    meg = len(feor) - len(lefedve) - len(eredmeny)
    if meg > 0:
        print(f"MEG HATRALEVO: {meg} — futtasd ujra a scriptet a folytatashoz.")


if __name__ == "__main__":
    main()
