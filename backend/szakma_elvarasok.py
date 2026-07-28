"""Egy szakma elvárásai a kinyert hirdetéstételekből.

Ez váltja le a `keszsegek` / `hirdetes_keszseg` páros szerepét: nem címkéket
használunk, hanem azt, amit a munkáltatók ténylegesen leírtak.

Miért nem a teljes mondat az egység: egész mondatok alig ismétlődnek. A
bolti eladó 388 hirdetésében 208 különböző tétel van, és a leggyakoribb is
csak 18-ban szerepel. Ezért a mondatokon BELÜLI kifejezéseket számoljuk --
de csak a `feladat` és `elvaras` szekciókból, tehát a bér, a marketing és a
cégbemutatkozás nem keveredik bele. Ez a régi megoldásban nem volt így.

Minden kifejezéshez megőrizzük a forrásmondatot, hogy idézni tudjuk:
„ezt 43 hirdetés kéri, például így: …"

Nulla modellhívás.
"""

from collections import Counter, defaultdict
from typing import Final

from backend.keszseg_felismero import normalizal
from utils.adatbazis import (
    hiteles_szarmasztott_sorok_hirdetesekhez,
    kliens,
)


# A CV-hez ezt a két szekciót mérjük. Az `ajanlat` a munkáltató ígérete, a
# `kultura` a hangneme, az `egyeb` a bemutatkozása -- egyik sem CV-hiány.
MERT_SZEKCIOK: Final = ("feladat", "elvaras")

MAX_SZO: Final = 3
MIN_SZO_HOSSZ: Final = 4

# Egyetlen szó csak akkor lehet önálló elvárás, ha elég hosszú. A magyar
# összetett szavak („árufeltöltés", „anyagmozgatás", „komissiózás") maguk
# is teljes fogalmak; a rövid szavak („rend", „áruk", „kézi") viszont
# önmagukban semmit nem mondanak.
MIN_ONALLO_SZO: Final = 8

# Ha a hosszabb kifejezés a rövidebb előfordulásainak legalább ekkora
# hányadát lefedi, akkor a hosszabb az igazi egység: a „pénztárgép" szinte
# mindig „pénztárgép kezelése" formában szerepel.
LEFEDES: Final = 0.6

# Ennyi KÜLÖNBÖZŐ mondatban kell szerepelnie. Ez választja el a valódi
# elvárást a sablonszövegtől: a „pénztárgép kezelése" sokféle
# megfogalmazásban tér vissza, a „Köszöntöd és körbevezeted vásárlóinkat"
# viszont egyetlen mondat, amit sok hirdetésbe bemásoltak. Gyakoriságban
# a kettő egyforma; a megfogalmazások számában nem.
MIN_FORRAS: Final = 3

# A szakma hirdetéseinek legalább ennyi százalékában szerepeljen.
MIN_SZAZALEK: Final = 3.0

# Ennyiszer legyen gyakoribb ebben a szakmában, mint az összes hirdetésben.
# Ez alatt általános szöveg, nem szakmai elvárás.
MIN_KIEMELKEDES: Final = 4.0

TOP: Final = 20


def _ngramok(szoveg: str) -> set[str]:
    szavak = [
        szo for szo in normalizal(szoveg).split() if len(szo) >= MIN_SZO_HOSSZ
    ]
    talalt = set()
    for hossz in range(1, MAX_SZO + 1):
        for kezdet in range(len(szavak) - hossz + 1):
            talalt.add(" ".join(szavak[kezdet : kezdet + hossz]))
    return talalt


def _tetelek(db, szakma_id: int | None) -> list[dict]:
    sorok: list[dict] = []
    kezdet = 0
    while True:
        kerdes = (
            db.table("hirdetes_tetel")
            .select(
                "id,hirdetes_id,szakma_id,szekcio,szoveg,"
                "snapshot_id,feldolgozo_verzio,forras_bizonyitek,"
                "forras_bizonyitek_kezdete,forras_bizonyitek_vege"
            )
            .in_("szekcio", list(MERT_SZEKCIOK))
            .order("id")
            .range(kezdet, kezdet + 999)
        )
        if szakma_id is not None:
            kerdes = kerdes.eq("szakma_id", szakma_id)
        adag = kerdes.execute().data or []
        sorok.extend(adag)
        if len(adag) < 1000:
            break
        kezdet += 1000
    return hiteles_szarmasztott_sorok_hirdetesekhez(db, sorok)


def _ossz_elofordulas(db) -> tuple[Counter, int]:
    """Az összes szakma tételeiből: melyik kifejezés hány hirdetésben van.

    Ez a viszonyítási alap. Ami mindenhol előfordul („önálló munkavégzés"),
    az egyik szakmára sem jellemző.
    """
    hirdetesenkent: dict[int, set[str]] = defaultdict(set)
    for sor in _tetelek(db, None):
        hirdetesenkent[sor["hirdetes_id"]].update(_ngramok(sor["szoveg"]))

    szamlalo: Counter = Counter()
    for kifejezesek in hirdetesenkent.values():
        szamlalo.update(kifejezesek)
    return szamlalo, len(hirdetesenkent)


def szakma_elvarasai(szakma_id: int | None) -> list[dict]:
    """A szakmára jellemző elvárások, gyakorisággal és példamondattal."""
    db = kliens()
    if not db or not szakma_id:
        return []

    sajat = _tetelek(db, szakma_id)
    if not sajat:
        return []

    hirdetesenkent: dict[int, set[str]] = defaultdict(set)
    pelda: dict[str, str] = {}
    megfogalmazasok: dict[str, set[str]] = defaultdict(set)
    for sor in sajat:
        kifejezesek = _ngramok(sor["szoveg"])
        hirdetesenkent[sor["hirdetes_id"]].update(kifejezesek)
        for kifejezes in kifejezesek:
            megfogalmazasok[kifejezes].add(normalizal(sor["szoveg"]))
            # A legrövidebb forrásmondatot őrizzük meg: az idézhető a
            # legjobban, mert nem tartalmaz felesleges környezetet.
            regi = pelda.get(kifejezes)
            if regi is None or len(sor["szoveg"]) < len(regi):
                pelda[kifejezes] = sor["szoveg"]

    darab = len(hirdetesenkent)
    sajat_szamlalo: Counter = Counter()
    for kifejezesek in hirdetesenkent.values():
        sajat_szamlalo.update(kifejezesek)

    ossz_szamlalo, ossz_hirdetes = _ossz_elofordulas(db)

    eredmeny = []
    for kifejezes, elofordulas in sajat_szamlalo.items():
        szavak = kifejezes.split()
        if len(szavak) == 1 and len(kifejezes) < MIN_ONALLO_SZO:
            continue
        # Sablonszöveg kiszűrése: egyetlen bemásolt mondat nem elvárás.
        if len(megfogalmazasok[kifejezes]) < MIN_FORRAS:
            continue
        szazalek = 100 * elofordulas / darab
        if szazalek < MIN_SZAZALEK:
            continue
        altalanos = ossz_szamlalo.get(kifejezes, 0) / max(ossz_hirdetes, 1)
        kiemelkedes = (elofordulas / darab) / max(altalanos, 1e-9)
        if kiemelkedes < MIN_KIEMELKEDES:
            continue
        eredmeny.append({
            "nev": kifejezes,
            "elofordulas": elofordulas,
            "szazalek": round(szazalek, 1),
            "kiemelkedes": round(kiemelkedes, 1),
            "pelda": pelda.get(kifejezes, ""),
        })

    # Gyakoriság ÉS kiemelkedés együtt: külön-külön egyik sem jó rangsor.
    eredmeny.sort(key=lambda sor: -(sor["szazalek"] * sor["kiemelkedes"]))
    return _atfedesek_nelkul(eredmeny)[:TOP]


def _atfedesek_nelkul(elvarasok: list[dict]) -> list[dict]:
    """Az egymást lefedő kifejezésekből a rövidebbet tartjuk meg.

    Egyetlen sokszor ismételt mondat különben elárasztja a listát: az
    „árufeldolgozás", „árufeldolgozás eredmény" és „árukihelyezés aktív
    eladásösztönzés" mind ugyanabból a kilenc hirdetésből jön, azonos
    gyakorisággal.

    Ha egy hosszabb kifejezés részét képező rövidebb már bent van, és
    legalább ugyanannyi hirdetésben szerepel, akkor a hosszabb nem tesz
    hozzá semmit -- a bővebb megfogalmazást a példamondat úgyis megőrzi.
    """
    # Ha a hosszabb kifejezés a rövidebb használatának nagy részét lefedi,
    # akkor a hosszabb az igazi egység -- a „pénztárgép" szinte mindig
    # „pénztárgép kezelése" formában szerepel, önmagában nem elvárás.
    elnyomott: set[str] = set()
    for rovid in elvarasok:
        rovid_szavak = set(rovid["nev"].split())
        for hosszu in elvarasok:
            if hosszu is rovid or len(hosszu["nev"]) <= len(rovid["nev"]):
                continue
            if not rovid_szavak < set(hosszu["nev"].split()):
                continue
            if hosszu["elofordulas"] >= LEFEDES * rovid["elofordulas"]:
                elnyomott.add(rovid["nev"])
                break

    megtartott: list[dict] = []
    # Egy sokszor ismételt mondat MINDEN szava azonos gyakoriságú lesz, és
    # külön tételként jelenne meg („Köszöntöd", „körbevezeted",
    # „vásárlóinkat"…). Forrásmondatonként ezért csak egy tétel maradhat.
    forrasok: set[tuple[str, int]] = set()

    for jelolt in sorted(elvarasok, key=lambda sor: len(sor["nev"].split())):
        if jelolt["nev"] in elnyomott:
            continue
        szavak = jelolt["nev"].split()
        lefedi = any(
            set(mar["nev"].split()) <= set(szavak)
            and mar["elofordulas"] >= jelolt["elofordulas"]
            for mar in megtartott
        )
        if lefedi:
            continue
        forras = (jelolt["pelda"], jelolt["elofordulas"])
        if forras in forrasok:
            continue
        forrasok.add(forras)
        megtartott.append(jelolt)

    # Az eredeti rangsor helyreáll: a szűrés csak elvett, nem rendezett át.
    sorrend = {sor["nev"]: i for i, sor in enumerate(elvarasok)}
    megtartott.sort(key=lambda sor: sorrend[sor["nev"]])
    return megtartott
