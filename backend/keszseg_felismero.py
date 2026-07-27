"""Készségfelismerés CV-szövegben, szinonimaszótárból.

Nulla modellhívás: a `public.keszseg_valtozat` táblában szereplő
kifejezéseket keressük a szövegben, szóhatáron. Ugyanarra a szövegre
mindig ugyanaz az eredmény, és ami nincs benne a szótárban, az látható
hiány -- nem véletlenszerű tévedés.

A normalizálásnak KARAKTERRE egyeznie kell a `public.keszseg_normalizal`
SQL-függvénnyel, különben a feltöltött és a keresett alak elcsúszik.
"""

import re

from utils.adatbazis import kliens, osszes_sor


# Ugyanaz a kilenc magyar ékezetes betű, mint az SQL `translate` hívásában.
_EKEZETEK = str.maketrans("áéíóöőúüű", "aeiooouuu")
_NEM_ERTELMES = re.compile(r"[^a-z0-9 -]")
_TOBB_SZOKOZ = re.compile(r"\s+")


def normalizal(szoveg: str) -> str:
    """Kisbetű, ékezet nélkül, csak betű/szám/szóköz/kötőjel, egy szóköz."""
    kisbetus = (szoveg or "").lower().translate(_EKEZETEK)
    tisztitott = _NEM_ERTELMES.sub(" ", kisbetus)
    return _TOBB_SZOKOZ.sub(" ", tisztitott).strip()


def valtozatok_betoltese() -> dict[str, int]:
    """A teljes szótár: normalizált kifejezés -> készség azonosító.

    Egyszer töltjük be, és sok szövegre használjuk: a felismerés utána
    már hálózat nélkül fut.
    """
    sorok = osszes_sor("keszseg_valtozat", "id, keszseg_id, normalizalt")
    return {
        sor["normalizalt"]: sor["keszseg_id"]
        for sor in sorok
        if sor.get("normalizalt") and sor.get("keszseg_id")
    }


# Ennyi kezdőkarakter alapján indexeljük a kifejezéseket. A magyar ragok a
# szó VÉGÉRE kerülnek, tehát az eleje ragozva is ugyanaz marad.
_KULCS_HOSSZ = 5

# A közös tő után ennyi karakter térhet el szavanként. Enélkül a
# „raktár" beletalálna a „raktározástechnológiába".
_MAX_RAG = 4

# Ennél rövidebb közös tövet nem fogadunk el: a rövid egyezés véletlen
# is lehet („ár" ⊂ „áru").
_MIN_TO = 5


def _kozos_elotag(egyik: str, masik: str) -> int:
    hossz = 0
    for a, b in zip(egyik, masik):
        if a != b:
            break
        hossz += 1
    return hossz


def _szo_egyezik(szoveg_szo: str, szotar_szo: str) -> bool:
    """Két szó ugyanarra a tőre megy-e vissza.

    Magyarban a rag ÉS a képző is a szó végére kerül, ezért a közös tövet
    nézzük, nem azt, hogy egyik előtagja-e a másiknak:

        pénztárgép / pénztárgépet   -> rag,   közös tő „pénztárgép"
        fejlesztő  / fejlesztés     -> képző, közös tő „fejleszt"

    A második eset nem előtag-viszony, mégis ugyanaz a szakma. A tő
    minimális hossza és a maradék korlátja védi a véletlen egyezéstől:
    „áru" nem lesz azonos az „árusítás"-sal.
    """
    if szoveg_szo == szotar_szo:
        return True
    kozos = _kozos_elotag(szoveg_szo, szotar_szo)
    if kozos < _MIN_TO:
        return False
    return (
        len(szoveg_szo) - kozos <= _MAX_RAG
        and len(szotar_szo) - kozos <= _MAX_RAG
    )


def index_epitese(valtozatok: dict[str, int]) -> dict:
    """Kereső index: az első szó kezdete -> a vele kezdődő kifejezések.

    Enélkül minden szövegre mind a ~7000 kifejezést végig kellene néznünk.
    """
    index: dict[str, list] = {}
    for kifejezes in valtozatok:
        szavak = kifejezes.split()
        if not szavak:
            continue
        index.setdefault(szavak[0][:_KULCS_HOSSZ], []).append((szavak, kifejezes))
    return index


def felismert_kifejezesek(
    szoveg: str,
    valtozatok: dict[str, int],
    index: dict | None = None,
) -> set[str]:
    """A szövegben előforduló szótári kifejezések, ragozott alakban is.

    Szóhatáron illesztünk -- az „ár" nem talál bele az „árurendezés"-be --,
    de a ragozott végződést elfogadjuk.
    """
    szavak = normalizal(szoveg).split()
    if index is None:
        index = index_epitese(valtozatok)

    talalt: set[str] = set()
    for kezdet, szo in enumerate(szavak):
        for frazis, kifejezes in index.get(szo[:_KULCS_HOSSZ], ()):
            if kezdet + len(frazis) > len(szavak):
                continue
            if all(
                _szo_egyezik(szavak[kezdet + eltolas], frazis[eltolas])
                for eltolas in range(len(frazis))
            ):
                talalt.add(kifejezes)
    return talalt


def felismert_keszseg_idk(szoveg: str, valtozatok: dict[str, int]) -> set[int]:
    """A szövegből kiolvasható készségek azonosítói."""
    return {
        valtozatok[kifejezes]
        for kifejezes in felismert_kifejezesek(szoveg, valtozatok)
    }


def valtozatok_szakmahoz(szakma_id: int | None) -> dict[str, int]:
    """A szakmára érvényes szótár: az általános mag + a szakma tanult sorai.

    Más szakma tanult sorait szándékosan kihagyjuk: a „vásárlók
    kiszolgálása" bolti eladónál mást jelent, mint ügyfélszolgálatnál.
    """
    db = kliens()
    if not db:
        return {}
    altalanos: dict[str, int] = {}
    szakmai: dict[str, int] = {}
    kezdet = 0
    while True:
        kerdes = (
            db.table("keszseg_valtozat")
            .select("id, keszseg_id, normalizalt, szakma_id")
            .order("id")
            .range(kezdet, kezdet + 999)
        )
        adag = (kerdes.execute().data) or []
        for sor in adag:
            sajat = sor.get("szakma_id")
            if sajat is None:
                altalanos.setdefault(sor["normalizalt"], sor["keszseg_id"])
            elif sajat == szakma_id:
                szakmai.setdefault(sor["normalizalt"], sor["keszseg_id"])
        if len(adag) < 1000:
            break
        kezdet += 1000

    # A szakmához tanult megfeleltetés ERŐSEBB az általánosnál: a „vásárlók
    # kiszolgálása" bolti eladónál mást jelent, mint ügyfélszolgálatnál, és
    # a szakma-specifikus sor mögött ott a bizonyíték is.
    return {**altalanos, **szakmai}


def keszseg_nevek(keszseg_idk: set[int]) -> dict[int, str]:
    """Azonosító -> megjelenítendő név, a kanonikus alakot előnyben részesítve."""
    db = kliens()
    if not db or not keszseg_idk:
        return {}
    idk = sorted(keszseg_idk)
    nevek: dict[int, str] = {}
    # Adagolva: a Supabase `in_` szűrője hosszú listánál elhasal.
    for kezdet in range(0, len(idk), 200):
        adag = idk[kezdet : kezdet + 200]
        valasz = (
            db.table("keszsegek")
            .select("id, nev, kanonikus")
            .in_("id", adag)
            .execute()
        )
        for sor in valasz.data or []:
            nevek[sor["id"]] = sor.get("kanonikus") or sor.get("nev") or ""
    return nevek
