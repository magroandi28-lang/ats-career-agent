"""Egy szakma valódi pozíciónevei a hirdetésekből.

A HR-es egyezéseket keres: ha a CV-ben egyetlen olyan pozíciónév sincs,
amilyet a hirdetések használnak, a pályázat elakad, mielőtt bárki elolvasná.
A hirdetéscímekben 11 000-nél több valódi megnevezés van — ez mondja meg,
milyen néven keresik a munkát a munkáltatók.

Nulla modellhívás.
"""

import re
from collections import Counter

from backend.keszseg_felismero import felismert_kifejezesek, normalizal
from utils.adatbazis import kliens


# A cím után álló pontosítások: „Bolti eladó - Részmunkaidő (6 órás)",
# „Full Stack PHP Developer (Tatabánya régió)", „.NET Developer @ Margo".
#
# Csak SZÓKÖZZEL határolt elválasztónál vágunk. A szó belsejében álló
# kötőjel a névhez tartozik: a „Totó-lottóértékesítő" és a „Full-Stack
# Developer" nem vágható ketté.
_TOLDALEK = re.compile(r"\s+(?:[-–|/]|@|\()\s*.*$|\s*\(.*$|,\s.*$")

# Ennyi leggyakoribb megnevezést adunk vissza.
TOP = 8

# Ez alatt nem tekintjük bevett megnevezésnek, csak egyedi címadásnak.
MIN_ELOFORDULAS = 2


def _tisztit(cim: str) -> str:
    """A cím lényege: a pozíció neve, a hozzátoldott pontosítások nélkül."""
    return _TOLDALEK.sub("", (cim or "").strip()).strip(" .,-–")


def _helyszinszavak(db) -> set[str]:
    """A hirdetések helyszínmezőiből kigyűjtött településnevek.

    Sok cím helyszínnel kezdődik („Budapest - Bolti eladó"), és a vágás
    után a helység maradna meg pozíciónévként. Nem listát írunk kézzel:
    a saját adatunkból tudjuk, mely szavak helyszínek.
    """
    szavak: set[str] = set()
    kezdet = 0
    while True:
        valasz = (
            db.table("hirdetesek").select("id, helyszin").order("id")
            .range(kezdet, kezdet + 999).execute()
        )
        adag = valasz.data or []
        for sor in adag:
            for szo in normalizal(sor.get("helyszin") or "").split():
                if len(szo) >= 4:
                    szavak.add(szo)
        if len(adag) < 1000:
            return szavak
        kezdet += 1000


def pozicionevek(szakma_id: int | None) -> list[dict]:
    """A szakma leggyakoribb pozíciónevei, előfordulással.

    A megjelenített alak a leggyakoribb írásmód („Bolti eladó", nem
    „BOLTI ELADÓ"), a csoportosítás viszont kis-nagybetűtől független.
    """
    db = kliens()
    if not db or not szakma_id:
        return []

    cimek: list[str] = []
    kezdet = 0
    while True:
        valasz = (
            db.table("hirdetesek").select("id, cim")
            .eq("szakma_id", szakma_id).order("id")
            .range(kezdet, kezdet + 999).execute()
        )
        adag = valasz.data or []
        cimek.extend(_tisztit(sor.get("cim") or "") for sor in adag)
        if len(adag) < 1000:
            break
        kezdet += 1000

    # Kulcs a normalizált alak, hogy a „Bolti eladó" és a „Bolti Eladó"
    # egy tételbe kerüljön; a kiírt alak a leggyakoribb írásmód.
    helyszinek = _helyszinszavak(db)
    csoportok: dict[str, Counter] = {}
    for cim in cimek:
        kulcs = normalizal(cim)
        if len(cim) < 3 or not kulcs:
            continue
        # Ami csupa helységnévből áll, az nem pozíciónév.
        if all(szo in helyszinek for szo in kulcs.split()):
            continue
        csoportok.setdefault(kulcs, Counter())[cim] += 1

    eredmeny = [
        {
            "nev": irasmodok.most_common(1)[0][0],
            "kulcs": kulcs,
            "elofordulas": sum(irasmodok.values()),
        }
        for kulcs, irasmodok in csoportok.items()
        if sum(irasmodok.values()) >= MIN_ELOFORDULAS
    ]
    eredmeny.sort(key=lambda sor: -sor["elofordulas"])
    return eredmeny[:TOP]


def cvben_szereplo(cv_szoveg: str, nevek: list[dict]) -> list[str]:
    """Melyik bevett pozíciónév szerepel ténylegesen a CV-ben.

    A meglévő szótő-illesztőt használjuk, tehát a „raktárosként dolgoztam"
    is találat a „raktáros" megnevezésre.
    """
    if not (cv_szoveg or "").strip() or not nevek:
        return []
    szotar = {sor["kulcs"]: i for i, sor in enumerate(nevek)}
    talalt = felismert_kifejezesek(cv_szoveg, szotar)
    return [sor["nev"] for sor in nevek if sor["kulcs"] in talalt]
