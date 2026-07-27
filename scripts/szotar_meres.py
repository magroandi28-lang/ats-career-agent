"""Megméri, mennyit ismer fel a készség-szinonimaszótár.

Mérce: a `hirdetes_keszseg` táblában MÁR hozzárendelt készségek. Ezekről
tudjuk a helyes választ, tehát ráengedhetjük a szótárat a hirdetés
szövegére, és megnézhetjük, hányat talál meg belőlük.

Nulla modellhívás, nulla költség, tetszőlegesen ismételhető.

Futtatás a projekt gyökeréből:
    python scripts/szotar_meres.py
"""

from collections import Counter
from pathlib import Path
import sys

# A projekt gyökere: enélkül a `backend` és `utils` csomag nem található,
# ha a szkriptet közvetlenül indítod.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.keszseg_felismero import (  # noqa: E402
    felismert_kifejezesek,
    index_epitese,
    normalizal,
    valtozatok_betoltese,
)
from utils.adatbazis import kliens, osszes_sor  # noqa: E402


# Ennyi hirdetésen mérünk. A teljes adatbázis is mehet, csak lassabb.
MINTA_MERET = 400


def main() -> int:
    db = kliens()
    if not db:
        print("Nincs adatbázis-kapcsolat.")
        return 1

    print("Szótár betöltése…")
    valtozatok = valtozatok_betoltese()
    index = index_epitese(valtozatok)
    print(f"  {len(valtozatok)} kifejezés")

    print("Címkézett hirdetések betöltése…")
    # A kapcsolótáblának nincs `id` oszlopa, ezért nem az `osszes_sor`
    # segédfüggvényt használjuk: itt a hirdetés-azonosító a rendezési kulcs.
    parok, kezdet = [], 0
    while True:
        valasz = (
            db.table("hirdetes_keszseg")
            .select("hirdetes_id, keszseg_id")
            .order("hirdetes_id")
            .range(kezdet, kezdet + 999)
            .execute()
        )
        adag = valasz.data or []
        parok.extend(adag)
        if len(adag) < 1000:
            break
        kezdet += 1000

    cimkek: dict[int, set[int]] = {}
    for sor in parok:
        cimkek.setdefault(sor["hirdetes_id"], set()).add(sor["keszseg_id"])
    print(f"  {len(cimkek)} hirdetéshez van címke")

    hirdetes_idk = sorted(cimkek)[:MINTA_MERET]
    szovegek: dict[int, str] = {}
    for kezdet in range(0, len(hirdetes_idk), 200):
        adag = hirdetes_idk[kezdet : kezdet + 200]
        valasz = (
            db.table("hirdetesek")
            .select("id, cim, snippet")
            .in_("id", adag)
            .execute()
        )
        for sor in valasz.data or []:
            szovegek[sor["id"]] = f"{sor.get('cim') or ''} {sor.get('snippet') or ''}"

    # Ugyanaz a készség több azonosítón is szerepel az adatbázisban (pl.
    # „ügyfélszolgálat" háromszor). Ha azonosítót hasonlítanánk, a szótár
    # csak az egyik példányt találná el, a többit sosem -- ez önmagában
    # levinné az arányt. Ezért NÉV szintjén mérünk.
    keszseg_nev: dict[int, str] = {}
    for sor in osszes_sor("keszsegek", "id, nev, kanonikus"):
        nev = sor.get("kanonikus") or sor.get("nev") or ""
        keszseg_nev[sor["id"]] = normalizal(nev)

    talalt_osszesen = 0
    elvart_osszesen = 0
    nem_talalt: Counter = Counter()

    for hid in hirdetes_idk:
        szoveg = szovegek.get(hid)
        if not szoveg:
            continue
        elvart = {
            keszseg_nev.get(kid, "") for kid in cimkek[hid]
        } - {""}
        kifejezesek = felismert_kifejezesek(szoveg, valtozatok, index)
        talalt = {
            keszseg_nev.get(valtozatok[k], "") for k in kifejezesek
        } - {""}

        elvart_osszesen += len(elvart)
        talalt_osszesen += len(elvart & talalt)
        for hianyzo in elvart - talalt:
            nem_talalt[hianyzo] += 1

    if not elvart_osszesen:
        print("Nincs mérhető adat.")
        return 1

    arany = 100 * talalt_osszesen / elvart_osszesen
    print()
    print(f"Megvizsgált hirdetés:      {len(hirdetes_idk)}")
    print(f"Elvárt készség-előfordulás: {elvart_osszesen}")
    print(f"Ebből felismert:            {talalt_osszesen}")
    print(f"FELISMERÉSI ARÁNY:          {arany:.1f}%")

    if nem_talalt:
        print()
        print("A leggyakrabban ki nem szűrt készségek (ezek kellenek a szótárba):")
        for nev, darab in nem_talalt.most_common(25):
            print(f"  {darab:4d}x  {nev}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
