"""Besorolatlan kĂ©szsĂ©gek fogalomhoz rendelĂ©se beĂˇgyazĂˇssal â€” csak prĂłba.

CSAK OLVAS. Semmit nem Ă­r az adatbĂˇzisba: kiĂ­rja, mit rendelne hova, Ă©s
milyen biztosan. ElĹ‘bb lĂˇssuk, mit csinĂˇlna, Ă©s csak utĂˇna dĂ¶ntsĂĽnk.

A feladat itt szĹ±kebb Ă©s biztonsĂˇgosabb, mint a CV-illesztĂ©s: nem tetszĹ‘leges
szĂ¶vegpĂˇrokat hasonlĂ­tunk, hanem egy besorolatlan kĂ©szsĂ©get a MEGLĂ‰VĹ
fogalmak listĂˇjĂˇhoz. A â€žvĂˇsĂˇrlĂˇs â†” Ă©rtĂ©kesĂ­tĂ©s" tĂ­pusĂş csapda Ă­gy fel sem
merĂĽl, mert a rossz jelĂ¶lt nincs is a listĂˇn.

ElĹ‘feltĂ©tel: fut az Ollama, Ă©s letĂ¶ltĂ¶tted a bge-m3 modellt.

FuttatĂˇs a projekt gyĂ¶kerĂ©bĹ‘l:
    python scripts/fogalom_beagyazas_proba.py [mintaszam]
"""

from collections import Counter
from pathlib import Path
import sys

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.adatbazis import osszes_sor  # noqa: E402


OLLAMA = "http://localhost:11434/api/embed"
MODELL = "bge-m3"
ADAG = 64

# Ez alatt nem sorolunk be. InkĂˇbb maradjon besorolatlan, mint rossz helyre
# kerĂĽljĂ¶n: egy tĂ©ves fogalom minden CV-ben Ă©s minden hirdetĂ©sben hibĂˇzna.
KUSZOB = 0.85

MINTA = int(sys.argv[1]) if len(sys.argv) > 1 else 40


def beagyaz(szovegek: list[str]) -> list[list[float]]:
    vektorok = []
    for kezdet in range(0, len(szovegek), ADAG):
        valasz = requests.post(
            OLLAMA,
            json={"model": MODELL, "input": szovegek[kezdet : kezdet + ADAG]},
            timeout=300,
        )
        valasz.raise_for_status()
        vektorok.extend(valasz.json()["embeddings"])
        print(f"  {min(kezdet + ADAG, len(szovegek))}/{len(szovegek)}", end="\r")
    print()
    return vektorok


def normal(vektor: list[float]) -> list[float]:
    hossz = sum(x * x for x in vektor) ** 0.5
    return [x / hossz for x in vektor] if hossz else vektor


def main() -> int:
    print("KĂ©szsĂ©gek betĂ¶ltĂ©seâ€¦")
    sorok = osszes_sor("keszsegek", "id, nev, kanonikus, fogalom")
    fogalmak = sorted({s["fogalom"] for s in sorok if s.get("fogalom")})
    besorolatlan = [s for s in sorok if not s.get("fogalom")][:MINTA]
    print(f"  {len(fogalmak)} meglĂ©vĹ‘ fogalom, {len(besorolatlan)} vizsgĂˇlt kĂ©szsĂ©g\n")

    print("Fogalmak beĂˇgyazĂˇsaâ€¦")
    fogalom_vektorok = [normal(v) for v in beagyaz(fogalmak)]

    print("KĂ©szsĂ©gnevek beĂˇgyazĂˇsaâ€¦")
    nevek = [s["nev"] for s in besorolatlan]
    nev_vektorok = [normal(v) for v in beagyaz(nevek)]

    print()
    elfogadott = 0
    szamlalo: Counter = Counter()
    for sor, vektor in zip(besorolatlan, nev_vektorok):
        pontok = [
            (sum(a * b for a, b in zip(vektor, fv)), fogalom)
            for fv, fogalom in zip(fogalom_vektorok, fogalmak)
        ]
        pontok.sort(reverse=True)
        legjobb, masodik = pontok[0], pontok[1]
        dontes = "BESOROL" if legjobb[0] >= KUSZOB else "kihagy "
        if legjobb[0] >= KUSZOB:
            elfogadott += 1
        szamlalo[dontes] += 1
        print(f"  [{dontes}] {legjobb[0]:.3f}  {sor['nev'][:42]:44s} -> "
              f"{legjobb[1][:30]:32s} (2.: {masodik[1][:22]} {masodik[0]:.3f})")

    print()
    print(f"KĂĽszĂ¶b: {KUSZOB}")
    print(f"BesorolhatĂł: {elfogadott}/{len(besorolatlan)} "
          f"({100 * elfogadott / max(len(besorolatlan), 1):.0f}%)")
    print("\n(Nem Ă­rtunk adatbĂˇzisba.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
