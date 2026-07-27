"""A hirdetésszöveg feldarabolása a saját szerkezete mentén.

A munkáltató maga jelöli meg, mi feladat, mi elvárás és mi az, amit ő
kínál („Feladatok ~… ~… Elvárások ~…"). A korábbi kinyerés ezt eldobta,
és rövid címkéket gyártott helyette — így veszett el, hogy a „hűtött
raktári munkavégzés" munkakörülmény, a „pénztárgép kezelése" pedig feladat.

Itt a felsorolás elemeit ÚGY tartjuk meg, ahogy a munkáltató leírta, és
megjegyezzük, melyik szekcióból származnak.

Nulla modellhívás.
"""

import re
from typing import Final


# A szekciócímek, ahogy a hirdetésekben előfordulnak. Több változatot is
# fel kell ismerni: nincs egységes szóhasználat a portálokon.
SZEKCIOK: Final = [
    ("feladat", r"(?:fő\s*)?feladat(?:ok|aid|od|aim|köröd)?\s*:?"
                r"|amiben számítunk a segítségedre\s*:?"
                r"|munkád során\s*:?|mit fogsz csinálni\s*:?"
                r"|munkakör(?:i)? leírás\s*:?|az állás leírása\s*:?"),
    ("elvaras", r"(?:elvárás(?:ok|aink)?|amit elvárunk|téged keresünk"
                r"|követelmények|amivel rendelkezel|amit tőled várunk"
                r"|téged várunk, ha|akkor keresünk téged, ha|ha rendelkezel"
                r"|elvárt (?:iskolai )?végzettség|előny, amivel rendelkezem"
                r"|szükséges (?:tapasztalat|végzettség))\s*:?"),
    # Csak olyan cím kerülhet ide, ami mondat közben nem fordul elő. A
    # „fizetés" és a „feltételek" például nem: azok a szöveg belsejében is
    # állnak, és kettévágnák a tételt. A bért tartalom alapján ismerjük fel.
    ("ajanlat", r"(?:amit (?:kínálunk|nyújtunk|ajánlunk|biztosítunk|adunk)"
                r"|amit tőlünk kapsz|juttatások|amiért megéri nálunk"
                r"|bérezés|munkakörülmények|bér és juttatás"
                r"|amiért érdemes|foglalkoztatás típusa)\s*:?"),
]
_SZEKCIO_MINTA: Final = re.compile(
    "|".join(f"(?P<{nev}>{minta})" for nev, minta in SZEKCIOK), re.IGNORECASE
)

# A hirdetés által kitett felsorolásjelek.
_ELEM_HATAR: Final = re.compile(r"\s*[~•*;]\s*|\s+-\s+|\n\s*[-–]\s*")

_NAGYBETU: Final = "AÁBCDEÉFGHIÍJKLMNOÓÖŐPQRSTUÚÜŰVWXYZ"

# A rövidített szöveg elejéről és végéről maradt csonka jelek.
_CSONKA: Final = re.compile(r"^\.{2,}|\.{2,}$|^…|…$")

# Portál-metaadat, nem a hirdetés tartalma.
_ZAJ: Final = re.compile(
    r"^(?:apply by|working hours|állománycsoport|munkakör kiegészítése"
    r"|kapcsolódó nyertes pályázat|felajánlott havi|jelentkezés"
    r"|\d[\d\s.,-]*)\b",
    re.IGNORECASE,
)

# Pénzről szóló tétel: ez mindig a munkáltató ajánlata, akármelyik szekció
# alatt szerepel. Sok hirdetés a bért az elvárások közé írja, és onnan
# „hiányozna" egy CV-ből -- ami képtelenség.
_PENZ: Final = re.compile(
    r"\b(?:brutt[oó]|nett[oó]|\d[\d\s.]*\s*(?:ft|forint)|órabér|orabor"
    r"|fizetés|jövedelem|bérpótlék|jutalék|prémium|cafeteria|bérezés"
    r"|költségtérítés|béren kívüli|bérlet|utazási támogatás"
    r"|szállás|munkába járás)\b",
    re.IGNORECASE,
)

# Cégjellemző szöveg: nem feladat és nem elvárás, hanem az, ahogy a
# munkáltató beszél magáról és a jelöltről. Nem zaj -- ebből derül ki,
# milyen munkahelyre készül az ember, és ez az ajánlásnál számít.
#
# Két jel árulja el: az érzelmi-értékelő szóhasználat („nagyszerű",
# „élmény", „büszke"), és a jelöltet megszólító, kérdő fordulat
# („Szeretsz…?", „Szeretnél…?").
_KULTURA: Final = re.compile(
    r"\b(?:nagyszerű|kiemelkedő|szenvedély|büszke|élmény|inspirál"
    r"|fiatalos|dinamikus|barátságos|támogató|családias|összetart"
    r"|értékeink|küldetés|siker(?:es|ünk)?|közösség|jó hangulat"
    r"|szeretsz|szeretnél|csatlakozz|várunk téged|legyél a|nálunk)\b",
    re.IGNORECASE,
)

# Ennél rövidebb töredék nem hordoz jelentést, ennél hosszabb pedig már
# nem egyetlen tétel, hanem bekezdés.
MIN_HOSSZ: Final = 12
MAX_HOSSZ: Final = 160


def _nagybetus(szo: str) -> bool:
    return bool(szo) and szo[0] in _NAGYBETU


def _mondatokra(resz: str) -> list[str]:
    """Jelöletlen felsorolás szétszedése nagybetűváltásnál.

    „…kiszolgálása Pénztárkezelés Árufeltöltés…" -> három tétel.

    Csak akkor vágunk, ha a nagybetűs szó ELŐTT kisbetűs szó áll. Két
    nagybetűs szó között nem: a „Spar Partner" és a „HACCP előírások"
    egyben marad. Ez regexszel nem fejezhető ki tisztán, mert a feltétel
    az előző SZÓRA vonatkozik, nem az előző betűre.

    ISMERT KORLÁT: emiatt a „Pénztárkezelés Árufeltöltés" is egyben marad,
    pedig az két tétel. A két eset szövegből megkülönböztethetetlen. Inkább
    összevonva hagyunk két elvárást, mint hogy egy cégnevet kettévágjunk:
    az összevont tétel szavaira a szótő-illesztő így is talál, a kettévágott
    tulajdonnév viszont értelmét veszti.
    """
    szavak = resz.split()
    if not szavak:
        return []

    darabok: list[list[str]] = [[szavak[0]]]
    for elozo, szo in zip(szavak, szavak[1:]):
        uj_tetel = (
            _nagybetus(szo)
            and not _nagybetus(elozo)
            # Névelő vagy kötőszó után a mondat folytatódik, nem új tétel
            # kezdődik: „Kiszolgálás a Spar üzletben".
            and len(elozo) > 2
            and not elozo.endswith((":", ",", "és", "vagy"))
            and len(szo) > 3
        )
        if uj_tetel:
            darabok.append([szo])
        else:
            darabok[-1].append(szo)
    return [" ".join(darab) for darab in darabok]


def bontas(szoveg: str) -> list[tuple[str, str]]:
    """(szekció, tétel) párok a hirdetés szövegéből.

    A szekció `feladat`, `elvaras`, `ajanlat` vagy `egyeb`. Az `egyeb` a
    szekciócím előtti rész: jellemzően a cég bemutatkozása.
    """
    if not szoveg:
        return []

    hatarok = [
        (m.start(), m.end(), m.lastgroup)
        for m in _SZEKCIO_MINTA.finditer(szoveg)
    ]

    szakaszok: list[tuple[str, str]] = []
    if not hatarok:
        szakaszok.append(("egyeb", szoveg))
    else:
        if hatarok[0][0] > 0:
            szakaszok.append(("egyeb", szoveg[: hatarok[0][0]]))
        for i, (_kezdet, veg, nev) in enumerate(hatarok):
            kovetkezo = hatarok[i + 1][0] if i + 1 < len(hatarok) else len(szoveg)
            szakaszok.append((nev, szoveg[veg:kovetkezo]))

    elemek: list[tuple[str, str]] = []
    for szekcio, resz in szakaszok:
        for jelolt in _ELEM_HATAR.split(resz):
            for nyers in _mondatokra(jelolt or ""):
                tiszta = _CSONKA.sub("", nyers).strip(" .,;:")
                tiszta = re.sub(r"\s+", " ", tiszta)
                if not (MIN_HOSSZ <= len(tiszta) <= MAX_HOSSZ):
                    continue
                if _ZAJ.match(tiszta):
                    continue
                elemek.append((_atsorolas(szekcio, tiszta), tiszta))
    return elemek


def _atsorolas(szekcio: str, tetel: str) -> str:
    """A tartalom felülírhatja azt, hogy a munkáltató hova írta.

    Két eset van, és mindkettő azért kell, mert különben olyasmit
    hiányolnánk egy CV-ből, ami nem a jelöltről szól:

    A pénz mindig ajánlat -- a bér nem a jelölt tulajdonsága.
    A cégjellemző szöveg mindig kultúra -- a „nagyszerű vásárlói élményt
    nyújtani" nem elvégzendő feladat, hanem a munkahely önjellemzése.
    """
    if _PENZ.search(tetel):
        return "ajanlat"
    if _KULTURA.search(tetel) or tetel.rstrip().endswith("?"):
        return "kultura"
    return szekcio


def van_szerkezet(szoveg: str) -> bool:
    """Megjelölte-e a munkáltató, mi feladat és mi elvárás."""
    return bool(_SZEKCIO_MINTA.search(szoveg or ""))
