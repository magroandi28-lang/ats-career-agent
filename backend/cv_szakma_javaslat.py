# -*- coding: utf-8 -*-
"""Célmunkakör-javaslat a CV szövegéből.

MIÉRT KELL: a célmunkakör nélkül egyetlen szolgáltatás sem fut -- a
CV-átvizsgálás, a piaci körkép és az álláskeresés mind ehhez viszonyít.
Eddig be kellett gépelni, pedig a CV-ben ott vannak a pozíciónevek
(„Bolti eladó — Tesco, 2019–2023").

MIÉRT NEM MODELLEL: ugyanaz a `Besorolo` végzi, ami a hirdetéscímeket
szakmához köti. Determinisztikus, ingyenes, és mérve 99,5%-os
önkonzisztenciájú. Amit javasol, az megmagyarázható: látszik, a CV melyik
sora hozta.

MIÉRT CSAK JAVASLAT: a célmunkakör NEM azonos a jelenlegivel. Aki bolti
eladóként dolgozik, de raktárosnak menne, annak a célja a raktáros. A CV
csak azt mondja meg, mi VOLT -- a döntés a felhasználóé. Ezért ez a modul
javaslatot ad, és soha nem ír profilt.
"""

import re
from collections import Counter

from backend.szakma_besorolo import Besorolo
from utils.adatbazis import kliens

# Iskolát vagy fokozatot jelölő szavak. Ahol ezek szerepelnek, ott
# végzettség áll, nem munkakör.
VEGZETTSEG_MINTA = re.compile(
    r"\b(bsc|msc|ba|ma|phd|okj|egyetem|főiskola|iskola|gimnázium|"
    r"szakközép|szakgimn|végzettség|diploma|képzés|tanfolyam|szakma)",
    re.IGNORECASE,
)

# A pozíciónevet a cégnévtől és az évszámtól elválasztó jelek.
SZETVAGO_MINTA = re.compile(r"\s[-–—|@]\s|\s{2,}|,\s")

# A CV-ben a pozíciónevek külön sorban állnak. Ennél hosszabb sor már
# mondat, nem munkakör -- azt ne próbáljuk címként értelmezni.
MAX_SOR_HOSSZ = 80

# Ennyi javaslatot adunk vissza. Több választék csak zavarna: a felhasználó
# egy kattintással dönt, vagy beír mást.
MAX_JAVASLAT = 3


def _mind(db, tabla: str, mezok: str) -> list[dict]:
    sorok, kezdet = [], 0
    while True:
        adag = (db.table(tabla).select(mezok)
                  .range(kezdet, kezdet + 999).execute().data or [])
        sorok += adag
        if len(adag) < 1000:
            return sorok
        kezdet += 1000


_besorolo: Besorolo | None = None


def _besorolo_epit() -> Besorolo | None:
    """A szótár egyszer épül fel, utána a folyamat élettartamáig él."""
    global _besorolo
    if _besorolo is not None:
        return _besorolo
    db = kliens()
    if db is None:
        return None
    foglalkozasok = _mind(
        db, "esco_foglalkozas",
        "uri, nev, isco_kod, alt_nevek, nev_en, alt_nevek_en")
    for f in foglalkozasok:
        f["alt_nevek"] = (list(f.get("alt_nevek") or [])
                          + list(f.get("alt_nevek_en") or []))
    _besorolo = Besorolo(
        foglalkozasok,
        _mind(db, "szakmak", "id, nev"),
        _mind(db, "szakma_esco", "szakma_id, foglalkozas_uri"),
    )
    return _besorolo


def celmunkakor_javaslatok(cv_szoveg: str) -> list[dict]:
    """A CV soraiból felismert szakmák, gyakoriság szerint.

    Visszaad: [{"szakma": str, "bizonyitek": str, "elofordulas": int}, …]
    Üres lista, ha semmit nem ismert fel -- ilyenkor kérdezni kell.
    """
    besorolo = _besorolo_epit()
    if besorolo is None or not (cv_szoveg or "").strip():
        return []

    talalatok: Counter = Counter()
    bizonyitek: dict[str, str] = {}
    for nyers in cv_szoveg.splitlines():
        sor = nyers.strip(" \t-–—•*·")
        if not sor or len(sor) > MAX_SOR_HOSSZ:
            continue
        # A VÉGZETTSÉG NEM MUNKAKÖR. E nélkül a „Kereskedelmi
        # szakközépiskola" sorból árufeltöltő lett, a „Mérnökinformatikus
        # BSc"-ből IT rendszermérnök. Rövid, stabil lista: ezek a szavak
        # iskolát vagy fokozatot jelölnek, nem pozíciót.
        if VEGZETTSEG_MINTA.search(sor):
            continue

        # A pozíciónév a sor ELEJÉN áll, a cégnév és az évszám utána:
        # „Bolti eladó - Tesco Hipermarket, 2019-2023". Az első elválasztóig
        # vágunk, különben a hosszú sor elnyomja a munkakört.
        cim = SZETVAGO_MINTA.split(sor, maxsplit=1)[0].strip()
        if not cim:
            continue

        talalat = besorolo.besorol(cim)
        if talalat is None or not talalat.szakma_nev:
            continue

        # A megmaradt rész NAGYRÉSZT maga a munkakör legyen, ne csak
        # tartalmazzon egy felismerhető szót.
        if len(talalat.cimke) * 2 < len(cim):
            continue
        talalatok[talalat.szakma_nev] += 1
        # Az ELSŐ előfordulást őrizzük meg bizonyítékként: a CV-ben a
        # legfrissebb pozíció áll elöl, és arra hivatkozni a legérthetőbb.
        bizonyitek.setdefault(talalat.szakma_nev, sor)

    return [
        {"szakma": nev, "bizonyitek": bizonyitek[nev], "elofordulas": darab}
        for nev, darab in talalatok.most_common(MAX_JAVASLAT)
    ]
