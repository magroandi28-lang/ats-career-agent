"""A készség-szinonimaszótár tanuló rétege — modell nélkül, szakmánként.

Amit csinál: megkeresi, mely kifejezések járnak együtt következetesen egy
készséggel EGY ADOTT SZAKMÁN BELÜL, és azokat felveszi a szótárba.

Miért szakmánként: a „vásárlók kiszolgálása" bolti eladónál eladói
készség, ügyfélszolgálati munkatársnál ügyfélszolgálat. Szakma nélkül
eldönthetetlen lenne, szakmán belül viszont az adat megmondja.

Miért nem terjed tovább a rossz címke: egy kifejezés csak akkor kerül be,
ha sok hirdetésben, következetesen ugyanahhoz a készséghez tartozik. Egyedi
tévedés nem éri el a küszöböt.

A tanult sorok minden futásnál törlődnek és újraszámolódnak: a tábla
generált, nem gyűjtött.

Futtatás a projekt gyökeréből:
    python scripts/szotar_tanulo.py
"""

from collections import Counter, defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.keszseg_felismero import (  # noqa: E402
    index_epitese,
    felismert_kifejezesek,
    normalizal,
    valtozatok_betoltese,
)
from utils.adatbazis import kliens  # noqa: E402


# Egy kifejezés legfeljebb ennyi szóból állhat.
MAX_SZO = 3

# Ennyi hirdetésben kell szerepelnie a szakmán belül, hogy egyáltalán
# számoljunk vele. Kevesebb előfordulásból nem lehet mintát látni.
MIN_TAMOGATAS = 5

# A kifejezést tartalmazó hirdetéseknek legalább ekkora hányada legyen
# ugyanazzal a készséggel címkézve. Ez a kapu szűri ki a kétértelműt.
MIN_PONTOSSAG = 0.70

# Ennél rövidebb szó nem lehet önálló kifejezés: a töltelékszavakat
# („és", „a", „egy") semmiképp ne tanuljuk meg.
MIN_SZO_HOSSZ = 4


def lapozva(db, tabla: str, mezok: str, rendez: str) -> list:
    sorok, kezdet = [], 0
    while True:
        valasz = (
            db.table(tabla).select(mezok).order(rendez)
            .range(kezdet, kezdet + 999).execute()
        )
        adag = valasz.data or []
        sorok.extend(adag)
        if len(adag) < 1000:
            return sorok
        kezdet += 1000


def ngramok(szoveg: str) -> set[str]:
    """A szöveg 1-3 szavas, normalizált kifejezései."""
    szavak = [
        szo for szo in normalizal(szoveg).split()
        if len(szo) >= MIN_SZO_HOSSZ
    ]
    talalt = set()
    for hossz in range(1, MAX_SZO + 1):
        for kezdet in range(len(szavak) - hossz + 1):
            talalt.add(" ".join(szavak[kezdet : kezdet + hossz]))
    return talalt


# Minden ötödik hirdetés vizsgaanyag: ezekből SOHA nem tanulunk, csak
# mérünk rajtuk. Az azonosító szerinti osztás determinisztikus -- ugyanaz
# a hirdetés mindig ugyanabba a csoportba esik, futásról futásra.
VIZSGA_OSZTO = 5


def vizsgaanyag(hirdetes_id: int) -> bool:
    return hirdetes_id % VIZSGA_OSZTO == 0


def _mag_betoltese(db) -> dict[str, int]:
    """Csak a nem tanult sorok: a generált mag és a kézzel felvett alakok."""
    valtozatok, kezdet = {}, 0
    while True:
        valasz = (
            db.table("keszseg_valtozat")
            .select("id, keszseg_id, normalizalt")
            .in_("forras", ["mag", "kezi"])
            .order("id")
            .range(kezdet, kezdet + 999)
            .execute()
        )
        adag = valasz.data or []
        for sor in adag:
            valtozatok.setdefault(sor["normalizalt"], sor["keszseg_id"])
        if len(adag) < 1000:
            return valtozatok
        kezdet += 1000


def _vizsga(db, hirdetesek, cimkek, valtozatok, ujak) -> int:
    """Mérés kizárólag a vizsgaanyagon, amit a tanuló sosem látott."""
    bovitett = dict(valtozatok)
    for sor in ujak:
        bovitett.setdefault(sor["normalizalt"], sor["keszseg_id"])
    index = index_epitese(bovitett)

    # Név szinten mérünk: ugyanaz a készség több azonosítón is szerepel.
    keszseg_nev: dict[int, str] = {}
    for sor in lapozva(db, "keszsegek", "id, nev, kanonikus", "id"):
        keszseg_nev[sor["id"]] = normalizal(
            sor.get("kanonikus") or sor.get("nev") or ""
        )

    elvart_osszesen = talalt_osszesen = 0
    # A kihagyottak közül hánynak nincs EGYETLEN közös szava sem a
    # hirdetésszöveggel. Ezekhez jelentés kell, szótár sosem elég -- ez adja
    # a lexikai módszerek felső korlátját.
    remenytelen = 0
    for sor in hirdetesek:
        if not vizsgaanyag(sor["id"]) or not cimkek.get(sor["id"]):
            continue
        szoveg = f"{sor.get('cim') or ''} {sor.get('snippet') or ''}"
        szoveg_szavai = set(normalizal(szoveg).split())
        elvart = {keszseg_nev.get(kid, "") for kid in cimkek[sor["id"]]} - {""}
        talalt = {
            keszseg_nev.get(bovitett[kif], "")
            for kif in felismert_kifejezesek(szoveg, bovitett, index)
        } - {""}
        elvart_osszesen += len(elvart)
        talalt_osszesen += len(elvart & talalt)
        for nev in elvart - talalt:
            if not (set(nev.split()) & szoveg_szavai):
                remenytelen += 1

    if not elvart_osszesen:
        print("Nincs vizsgaanyag.")
        return 1

    print()
    print(f"Vizsga-előfordulás:  {elvart_osszesen}")
    print(f"Ebből felismert:     {talalt_osszesen}")
    print(f"IGAZI ARÁNY:         {100 * talalt_osszesen / elvart_osszesen:.1f}%")

    kihagyott = elvart_osszesen - talalt_osszesen
    elerheto = elvart_osszesen - remenytelen
    print()
    print(f"Ebből szótárral elérhetetlen (nincs közös szó): {remenytelen}"
          f"  ({100 * remenytelen / elvart_osszesen:.1f}%)")
    print(f"Elvi felső korlát szótárral: {100 * elerheto / elvart_osszesen:.1f}%")
    if elerheto:
        print(f"A LEHETSÉGESBŐL TELJESÍTVE: "
              f"{100 * talalt_osszesen / elerheto:.1f}%")
    print(f"Még megszerezhető szótárral: {kihagyott - remenytelen} előfordulás")
    print("\n(Nem írtunk adatbázisba.)")
    return 0


def main() -> int:
    # `--ellenorzes`: a vizsgaanyagot kihagyja a tanulásból, és NEM ír
    # adatbázisba. Így megmérhető, mit tud a szótár olyan hirdetésen,
    # amit sosem látott.
    ellenorzes = "--ellenorzes" in sys.argv

    db = kliens()
    if not db:
        print("Nincs adatbázis-kapcsolat.")
        return 1

    if ellenorzes:
        print("ELLENŐRZŐ FUTÁS: a vizsgaanyag kimarad, adatbázisba nem írunk.\n")

    print("Meglévő szótár betöltése…")
    if ellenorzes:
        # A korábban beírt `tanult` sorok a TELJES anyagból készültek, tehát
        # a vizsgahirdetéseket is látták. Ha bennhagynánk, saját magunkat
        # vizsgáztatnánk a puskával -- csak az emberi/generált magot vesszük.
        valtozatok = _mag_betoltese(db)
    else:
        valtozatok = valtozatok_betoltese()
    index = index_epitese(valtozatok)
    print(f"  {len(valtozatok)} kifejezés")

    print("Hirdetések és címkék betöltése…")
    hirdetesek = lapozva(db, "hirdetesek", "id, szakma_id, cim, snippet", "id")
    parok = lapozva(db, "hirdetes_keszseg", "hirdetes_id, keszseg_id", "hirdetes_id")

    cimkek: dict[int, set[int]] = defaultdict(set)
    for sor in parok:
        cimkek[sor["hirdetes_id"]].add(sor["keszseg_id"])

    szakma_hirdetesei: dict[int, list] = defaultdict(list)
    for sor in hirdetesek:
        if not (sor.get("szakma_id") and cimkek.get(sor["id"])):
            continue
        if ellenorzes and vizsgaanyag(sor["id"]):
            continue
        szakma_hirdetesei[sor["szakma_id"]].append(sor)
    print(f"  {len(szakma_hirdetesei)} szakma, {len(hirdetesek)} hirdetés")

    ujak = []
    for szakma_id, sorok in szakma_hirdetesei.items():
        if len(sorok) < MIN_TAMOGATAS:
            continue

        # kifejezés -> a szakma mely hirdetéseiben szerepel
        elofordulas: dict[str, list[int]] = defaultdict(list)
        for sor in sorok:
            szoveg = f"{sor.get('cim') or ''} {sor.get('snippet') or ''}"
            # Az általános szótár találatait NEM zárjuk ki: ugyanaz a
            # kifejezés a szakmán belül más készséget jelenthet, és a
            # szakma-specifikus megfeleltetés a pontosabb. Korábban ezek
            # kimaradtak, és emiatt veszett el pl. az „áruk kirakása".
            for kifejezes in ngramok(szoveg):
                elofordulas[kifejezes].append(sor["id"])

        for kifejezes, hirdetes_idk in elofordulas.items():
            if len(hirdetes_idk) < MIN_TAMOGATAS:
                continue

            # Mely készségek járnak együtt ezzel a kifejezéssel?
            szamlalo: Counter = Counter()
            for hid in hirdetes_idk:
                szamlalo.update(cimkek.get(hid, ()))
            if not szamlalo:
                continue

            keszseg_id, egyutt = szamlalo.most_common(1)[0]
            pontossag = egyutt / len(hirdetes_idk)
            if pontossag < MIN_PONTOSSAG:
                continue

            ujak.append({
                "keszseg_id": keszseg_id,
                "szakma_id": szakma_id,
                "valtozat": kifejezes,
                "normalizalt": kifejezes,
                "forras": "tanult",
                "tamogatas": len(hirdetes_idk),
                "pontossag": round(pontossag, 4),
            })

    print(f"\nTanult változat: {len(ujak)}")
    if not ujak:
        return 0

    if ellenorzes:
        return _vizsga(db, hirdetesek, cimkek, valtozatok, ujak)

    print("Korábbi tanult sorok törlése…")
    db.table("keszseg_valtozat").delete().eq("forras", "tanult").execute()

    # Sima beszúrás: a tanult sorokat az előbb töröltük, a mag sorok pedig
    # szakma nélküliek, tehát más kulcson vannak. Az egyedi index kifejezésre
    # épül (`coalesce`), azt az ON CONFLICT nem tudná megcímezni.
    print("Beírás…")
    for kezdet in range(0, len(ujak), 400):
        db.table("keszseg_valtozat").insert(
            ujak[kezdet : kezdet + 400]
        ).execute()

    print(f"KÉSZ: {len(ujak)} tanult változat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
