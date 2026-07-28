# -*- coding: utf-8 -*-
"""Szakma -> ESCO-foglalkozás párosítás.

Két lépcső:

1. AUTOMATIKUS: normalizált névegyezés az ESCO preferált és alternatív
   nevei ellen. Ez biztos, ezért egyből bekerül ('pontos' / 'alternativ').

2. JAVASLAT: amire nincs pontos egyezés, ott szótő-átfedés alapján
   ajánlunk jelölteket. Ezeket EMBER hagyja jóvá -- a szkript magától
   nem ír be javaslatot, mert egy rossz párosítás az egész szakma
   mércéjét elrontaná.

Futtatás:
    python scripts/esco_szakma_parositas.py            # jelentés
    python scripts/esco_szakma_parositas.py --rogzit "szakma=uri" ...

Nulla modellhívás.
"""

import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.adatbazis import kliens  # noqa: E402


# Ennél rövidebb szó nem hordoz megkülönböztető jelentést.
MIN_SZO = 4
JAVASLAT = 3


def norm(szoveg: str) -> str:
    t = unicodedata.normalize("NFKD", (szoveg or "").lower())
    t = t.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", " ", t)


def szavak(szoveg: str) -> list[str]:
    return [sz for sz in norm(szoveg).split() if len(sz) >= MIN_SZO]


# Az egyszerű szótő-vágás (első 5 betű) összekeverte a „munkatárs"-at a
# „munkagépkezelő"-vel, és az „HR munkatárs"-hoz az „útépítő"-t ajánlotta.
# Ezért a rövidebb szónak a hosszabb elejét kell adnia, ÉS elég hosszúnak
# kell lennie hozzá képest -- így a „fejlesztő"/„fejlesztők" még egyezik,
# a „munka"/„munkagépkezelő" már nem.
ARANY = 0.6


def egyezik(a: str, b: str) -> bool:
    if a == b:
        return True
    rovid, hosszu = (a, b) if len(a) <= len(b) else (b, a)
    return hosszu.startswith(rovid) and len(rovid) / len(hosszu) >= ARANY


def hasonlosag(cel: list[str], cimke: list[str]) -> float:
    """Jaccard a fenti szóegyezéssel."""
    if not cel or not cimke:
        return 0.0
    talalt = sum(1 for sz in cel if any(egyezik(sz, m) for m in cimke))
    unio = len(cel) + len(cimke) - talalt
    return talalt / unio if unio else 0.0


def _mind(db, tabla: str, mezok: str) -> list[dict]:
    sorok, kezdet = [], 0
    while True:
        adag = db.table(tabla).select(mezok).range(kezdet, kezdet + 999).execute().data or []
        sorok += adag
        if len(adag) < 1000:
            return sorok
        kezdet += 1000


def main() -> int:
    db = kliens()
    if db is None:
        print("Nincs adatbázis-kapcsolat.")
        return 1

    parositott = {r["szakma_id"] for r in _mind(db, "szakma_esco", "szakma_id")}
    szakmak = _mind(db, "szakmak", "id, nev")
    hianyzo = [s for s in szakmak if s["id"] not in parositott]

    print(f"Szakma: {len(szakmak)} | párosítva: {len(parositott)} | "
          f"hiányzik: {len(hianyzo)}")
    if not hianyzo:
        return 0

    foglalkozasok = _mind(db, "esco_foglalkozas", "uri, nev, alt_nevek")
    # A jelöltkeresés a preferált ÉS az alternatív neveken is fut: az ESCO
    # gyakran másképp nevezi ugyanazt, mint a magyar hirdetéspiac.
    index = []
    for f in foglalkozasok:
        cimkek = [f["nev"]] + list(f.get("alt_nevek") or [])
        index.append((f["uri"], f["nev"], [(c, szavak(c)) for c in cimkek]))

    print()
    for s in hianyzo:
        cel = szavak(s["nev"])
        if not cel:
            continue
        pontok = []
        for uri, nev, cimkek in index:
            legjobb, honnan = 0.0, ""
            for cimke, sz in cimkek:
                pont = hasonlosag(cel, sz)
                if pont > legjobb:
                    legjobb, honnan = pont, cimke
            if legjobb > 0:
                pontok.append((legjobb, nev, honnan, uri))
        pontok.sort(reverse=True)

        print(f"{s['nev']}")
        if not pontok:
            print("    (nincs jelölt)")
        for pont, nev, honnan, uri in pontok[:JAVASLAT]:
            azonos = "" if honnan == nev else f"  [alt: {honnan}]"
            print(f"    {pont:.2f}  {nev}{azonos}")
            print(f"          {uri}")
        print()

    print("A jóváhagyott párokat így rögzítsd (megbizhatosag='kezi'):")
    print("    python scripts/esco_szakma_parositas.py --rogzit "
          "\"AI mérnök=http://data.europa.eu/esco/occupation/...\"")
    return 0


def rogzit(parok: list[str]) -> int:
    db = kliens()
    if db is None:
        return 1
    szakmak = {s["nev"]: s["id"] for s in _mind(db, "szakmak", "id, nev")}
    sorok = []
    for p in parok:
        if "=" not in p:
            print(f"Hibás formátum: {p}")
            return 1
        nev, uri = p.split("=", 1)
        if nev.strip() not in szakmak:
            print(f"Nincs ilyen szakma: {nev}")
            return 1
        sorok.append({"szakma_id": szakmak[nev.strip()],
                      "foglalkozas_uri": uri.strip(),
                      "megbizhatosag": "kezi"})
    db.table("szakma_esco").upsert(
        sorok, on_conflict="szakma_id,foglalkozas_uri").execute()
    print(f"Rögzítve: {len(sorok)} pár.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--rogzit":
        sys.exit(rogzit(sys.argv[2:]))
    sys.exit(main())
