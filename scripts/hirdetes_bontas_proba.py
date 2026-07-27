"""A hirdetésszöveg feldarabolása a saját szerkezete mentén — csak próba.

CSAK OLVAS. Semmit nem ír az adatbázisba.

A hirdetések maguk jelölik, mi feladat és mi elvárás („Feladatok ~… ~…
Elvárások ~…"). Az eddigi kinyerés ezt a szerkezetet eldobta, és rövid
címkéket gyártott helyette; ez a próba azt nézi meg, mi jön ki, ha a
felsorolás elemeit ÚGY tartjuk meg, ahogy a munkáltató leírta.

Futtatás a projekt gyökeréből:
    python scripts/hirdetes_bontas_proba.py "bolti eladó"
"""

from collections import Counter, defaultdict
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.adatbazis import osszes_sor  # noqa: E402


# A hirdetésekben előforduló szekciócímek. A sorrend számít: a hosszabb
# alakot kell előbb megtalálni, különben a rövidebb elnyeli.
SZEKCIOK = [
    ("feladat", r"(?:fő\s*)?feladat(?:ok|aid|od|aim|köröd)?\s*:?|"
                r"amiben számítunk a segítségedre\s*:?|"
                r"munkád során\s*:?|mit fogsz csinálni\s*:?|"
                r"munkakör(?:i)? leírás\s*:?"),
    ("elvaras", r"(?:elvárás(?:ok|aink)?|amit elvárunk|téged keresünk|"
                r"követelmények|amivel rendelkezel|"
                r"amit tőled várunk|téged várunk, ha|"
                r"akkor keresünk téged, ha|ha rendelkezel)\s*:?"),
    ("ajanlat", r"(?:amit (?:kínálunk|nyújtunk|ajánlunk)|"
                r"amit tőlünk kapsz|juttatások|amiért megéri nálunk)\s*:?"),
]
_SZEKCIO_MINTA = re.compile(
    "|".join(f"(?P<{nev}>{minta})" for nev, minta in SZEKCIOK), re.IGNORECASE
)

# Felsoroláshatárok. A hirdetések egy részében jelöletlen a felsorolás --
# ott a pontosvessző, illetve a „kisbetű + szóköz + Nagybetű" váltás jelzi az
# új tételt: „…kiszolgálása Pénztárkezelés Árufeltöltés…". Nagybetű után
# szándékosan NEM vágunk (Spar Partner, HACCP előírások).
_ELEM_HATAR = re.compile(
    r"\s*[~•*;]\s*"
    r"|\s+-\s+"
    r"|\n\s*[-–]\s*"
    r"|(?<=[a-záéíóöőúüű,])\s+(?=[A-ZÁÉÍÓÖŐÚÜŰ][a-záéíóöőúüű]{2,})"
)

# Nem a hirdetés tartalma, hanem a portál metaadata.
_ZAJ = re.compile(
    r"^(?:apply by|working hours|állománycsoport|munkakör kiegészítése|"
    r"kapcsolódó nyertes pályázat|felajánlott havi|jelentkezés|"
    r"\d[\d\s.,-]*)\b",
    re.IGNORECASE,
)

# Az első és utolsó elem gyakran csonka a rövidítés miatt.
_CSONKA = re.compile(r"^\.{2,}|\.{2,}$|^…|…$")

MIN_HOSSZ = 12
MAX_HOSSZ = 160


def darabol(szoveg: str) -> list[tuple[str, str]]:
    """(szekció, felsorolás-elem) párok a hirdetés szövegéből.

    Ami szekciócím előtt áll, az `egyeb`: általában a cég bemutatkozása.
    """
    if not szoveg:
        return []

    hatarok = [(m.start(), m.end(), m.lastgroup) for m in _SZEKCIO_MINTA.finditer(szoveg)]
    szakaszok = []
    if not hatarok:
        szakaszok.append(("egyeb", szoveg))
    else:
        if hatarok[0][0] > 0:
            szakaszok.append(("egyeb", szoveg[: hatarok[0][0]]))
        for i, (_kezd, veg, nev) in enumerate(hatarok):
            kovetkezo = hatarok[i + 1][0] if i + 1 < len(hatarok) else len(szoveg)
            szakaszok.append((nev, szoveg[veg:kovetkezo]))

    elemek = []
    for szekcio, resz in szakaszok:
        for nyers in _ELEM_HATAR.split(resz):
            tiszta = _CSONKA.sub("", nyers).strip(" .,;:")
            tiszta = re.sub(r"\s+", " ", tiszta)
            if not (MIN_HOSSZ <= len(tiszta) <= MAX_HOSSZ):
                continue
            if _ZAJ.match(tiszta):
                continue
            elemek.append((szekcio, tiszta))
    return elemek


def main() -> int:
    kert = sys.argv[1] if len(sys.argv) > 1 else "bolti eladó"

    szakmak = {s["nev"].casefold(): s["id"] for s in osszes_sor("szakmak", "id, nev")}
    szid = szakmak.get(kert.casefold())
    if szid is None:
        print(f"Nincs ilyen szakma: {kert}")
        return 1

    hirdetesek = [
        s for s in osszes_sor("hirdetesek", "id, szakma_id, cim, snippet")
        if s.get("szakma_id") == szid
    ]
    print(f"=== {kert}: {len(hirdetesek)} hirdetés\n")

    szekcionkent: dict[str, Counter] = defaultdict(Counter)
    van_szerkezet = 0
    for sor in hirdetesek:
        elemek = darabol(sor.get("snippet") or "")
        if any(szekcio != "egyeb" for szekcio, _ in elemek):
            van_szerkezet += 1
        for szekcio, elem in elemek:
            szekcionkent[szekcio][elem] += 1

    print(f"Kimondott szekció {van_szerkezet} hirdetésben "
          f"({100 * van_szerkezet / max(len(hirdetesek), 1):.0f}%)\n")

    cimke = {
        "feladat": "FELADATOK",
        "elvaras": "ELVÁRÁSOK",
        "ajanlat": "AMIT KÍNÁLNAK (nem CV-be való)",
        "egyeb": "SZEKCIÓ NÉLKÜL",
    }
    for szekcio in ("feladat", "elvaras", "ajanlat", "egyeb"):
        elemek = szekcionkent.get(szekcio)
        if not elemek:
            continue
        print(f"--- {cimke[szekcio]}  ({sum(elemek.values())} elem, "
              f"{len(elemek)} különböző)")
        for elem, darab in elemek.most_common(12):
            print(f"  {darab:4d}x  {elem}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
