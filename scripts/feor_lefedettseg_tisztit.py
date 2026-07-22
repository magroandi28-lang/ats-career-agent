# -*- coding: utf-8 -*-
"""FEOR-LEFEDETTSÉG TISZTÍTÁS — scripts/feor_lefedettseg_tisztit.py

A feor_lefedettseg_teszt.py NYERS eredménye HIBÁS volt azoknál a FEOR-
neveknél, amik " és -" mintájú, ELLIPTIKUS kötőjeles felsorolást
tartalmaznak (pl. "Baromfitartó és -tenyésztő", "Munka- és termelés-
szervező") — ilyenkor az EURES kereső NEM az adott kulcsszóra szűr,
hanem egy FIX, hamis (a teljes HU-állomány méretével megegyező) számot ad
vissza. ÉLŐBEN IGAZOLVA: "Baromfitartó és -tenyésztő" -> 741 találat, de a
visszaadott hirdetések teljesen irrelevánsak (oktatási asszisztens stb.) —
miközben "Baromfitartó" önmagában helyesen 0-t ad.

Ez a script minden gyanús (vessző vagy " és " a névben) FEOR-nevet
feldarabol tiszta, önmagában kereshető szegmensekre (a kötőjellel kezdődő/
végződő ELLIPTIKUS töredékeket eldobja — azok önmagukban nem érvényes
szó), majd EGYENKÉNT leteszteli őket, és a legjobb (legmagasabb, valós)
találatszámot menti — a keresett kifejezéssel együtt, hogy átlátható
maradjon, MIT kerestünk ténylegesen.

CSAK OLVAS és egy ÚJ JSON-fájlba ír (outputs/feor_lefedettseg_tisztitva.json)
— a szakmak táblát NEM módosítja.

Futtatás:
    python scripts/feor_lefedettseg_tisztit.py
"""

import concurrent.futures
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.adatbazis import kliens  # noqa: E402
from utils.eures import eures_kereses  # noqa: E402

NYERS_FAJL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "outputs", "feor_lefedettseg.json")
TISZTA_FAJL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "outputs", "feor_lefedettseg_tisztitva.json")
PARHUZAMOS = 8


def szegmensekre_bont(nev: str) -> list:
    """Egy FEOR-nevet önmagukban kereshető, TELJES (nem elliptikus-töredék)
    szegmensekre bont. Az " és -x" / "x- és" mintájú töredékeket eldobja."""
    reszek = re.split(r",| és ", nev)
    tiszta = []
    for r in reszek:
        r = r.strip()
        if not r:
            continue
        if r.startswith("-") or r.endswith("-"):
            continue  # elliptikus toredek, onmagaban ertelmetlen kereses
        tiszta.append(r)
    return tiszta or [nev]  # ha minden toredek volt, inkabb az eredetit probaljuk


def teszt_egy(kifejezes: str):
    r = eures_kereses(kifejezes, ["hu"], darab=3)
    return kifejezes, (r.get("talalatok", 0) if r.get("ok") else -1)


def main():
    db = kliens()
    if db is None:
        print("HIBA: nincs Supabase kapcsolat!")
        return

    feor = db.table("feor_lista").select("kod, nev").order("kod").execute().data or []
    szakmak = db.table("szakmak").select("feor_kod").execute().data or []
    lefedve = {s["feor_kod"] for s in szakmak if s.get("feor_kod")}
    nyers = json.load(open(NYERS_FAJL, encoding="utf-8")) if os.path.exists(NYERS_FAJL) else {}
    kesz = json.load(open(TISZTA_FAJL, encoding="utf-8")) if os.path.exists(TISZTA_FAJL) else {}

    hatralevo = [e for e in feor if e["kod"] not in lefedve]
    print(f"Ertekelendo FEOR-kategoria: {len(hatralevo)} | mar kesz (elozo futasbol): {len(kesz)}")

    # Gyanus nevek (vesszo vagy " es " -> lehet elliptikus kotojel-hiba), a mar kesz kihagyva
    gyanus = [e for e in hatralevo if e["kod"] not in kesz
              and ("," in e["nev"] or " és " in e["nev"])]
    tiszta_nevu = [e for e in hatralevo if e["kod"] not in kesz and e not in gyanus]

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    gyanus = gyanus[:limit]
    print(f"Gyanus nev (ujra kell tesztelni szegmensekre bontva): {len(gyanus)}")
    print(f"Eredetileg is tiszta nev (a nyers eredmeny megbizhato): {len(tiszta_nevu)}")

    # Az osszes egyedi tiszta szegmens osszegyujtese a gyanus nevekbol
    szegmens_map = {}  # kod -> [szegmensek]
    mind_szegmens = set()
    for e in gyanus:
        szegmensek = szegmensekre_bont(e["nev"])
        szegmens_map[e["kod"]] = szegmensek
        mind_szegmens.update(szegmensek)

    print(f"Egyedi szegmens leteszteleshez: {len(mind_szegmens)}")
    szegmens_eredmeny = {}
    mind_szegmens = list(mind_szegmens)
    with concurrent.futures.ThreadPoolExecutor(max_workers=PARHUZAMOS) as ex:
        for kif, talalat in ex.map(teszt_egy, mind_szegmens):
            szegmens_eredmeny[kif] = talalat

    # Vegeredmeny osszeallitasa (az elozo futasok eredmenyere ra-epitve)
    vegeredmeny = dict(kesz)
    for e in tiszta_nevu:
        vegeredmeny[e["kod"]] = {"nev": e["nev"], "kifejezes": e["nev"],
                                  "talalatok": nyers.get(e["kod"], -1)}
    for e in gyanus:
        szegmensek = szegmens_map[e["kod"]]
        legjobb_kif, legjobb_ertek = None, -1
        for sz in szegmensek:
            ertek = szegmens_eredmeny.get(sz, -1)
            if ertek > legjobb_ertek:
                legjobb_kif, legjobb_ertek = sz, ertek
        vegeredmeny[e["kod"]] = {"nev": e["nev"], "kifejezes": legjobb_kif,
                                  "talalatok": legjobb_ertek}

    with open(TISZTA_FAJL, "w", encoding="utf-8") as f:
        json.dump(vegeredmeny, f, ensure_ascii=False, indent=1)
    meg_hatra = len(hatralevo) - len(vegeredmeny)
    print(f"\nKESZ ({len(vegeredmeny)}/{len(hatralevo)} mentve). {TISZTA_FAJL}")
    if meg_hatra > 0:
        print(f"MEG HATRALEVO: {meg_hatra} — futtasd ujra a folytatashoz.")
    ertekek = [v["talalatok"] for v in vegeredmeny.values()]
    print(f"0 talalat: {sum(1 for v in ertekek if v==0)} | "
          f"1-9: {sum(1 for v in ertekek if 1<=v<=9)} | "
          f"10-49: {sum(1 for v in ertekek if 10<=v<=49)} | "
          f"50+: {sum(1 for v in ertekek if v>=50)} | "
          f"hiba: {sum(1 for v in ertekek if v==-1)}")


if __name__ == "__main__":
    main()
