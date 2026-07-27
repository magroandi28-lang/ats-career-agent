"""CV és szakma összevetése -- modellhívás nélkül.

Ez váltja ki az `agents.karrier_ugynok.ats_diagnozis_determinisztikus`
függvényt, ami a nevével ellentétben modellt hívott a készségfelismeréshez.

Mindkét oldalt ugyanaz a szabály olvassa: a hirdetéseket címkéző és a
CV-t vizsgáló ugyanabból a szinonimaszótárból dolgozik. Enélkül az
illeszkedési százalék nem lenne hiteles, mert két különböző mérce
eredményét hasonlítaná össze.

A visszaadott kulcsok megegyeznek a régi függvényével, hogy a hívók
változtatás nélkül működjenek tovább.
"""

from backend.keszseg_felismero import (
    felismert_keszseg_idk,
    normalizal,
    valtozatok_szakmahoz,
)
from backend.pozicionevek import cvben_szereplo, pozicionevek
from backend.szakma_elvarasok import szakma_elvarasai
from utils.adatbazis import kliens


# Ennyi leggyakoribb elvárást nézünk meg a szakmánál.
FIGYELT_KESZSEGEK = 20

# Ez alatt a hirdetésarány alatt NEM piaci elvárás, hanem egy-egy
# munkáltató sajátossága (pl. „pult kitörlése" egyetlen hirdetésben).
# Ilyet nem hiányolhatunk egy CV-ből.
PIACI_KUSZOB_SZAZALEK = 10

# E fölött a hirdetésarány fölött számít „fontos" elvárásnak: a szakma
# hirdetéseinek legalább felében szerepel.
FONTOS_SZAZALEK = 50


def _szakma_id(szakma: str) -> int | None:
    db = kliens()
    if not db or not szakma:
        return None
    valasz = (
        db.table("szakmak").select("id").ilike("nev", szakma.strip())
        .limit(1).execute()
    )
    return (valasz.data or [{}])[0].get("id")


def _felismert_fogalmak(keszseg_idk: set[int]) -> set[str]:
    """A felismert készségek gyűjtőfogalmai, normalizálva.

    Fogalom szinten hasonlítunk, mert a készséglistában ugyanaz a dolog
    több néven is szerepel („vevőkiszolgálás", „vevők kiszolgálása",
    „ügyfélszolgálat"). Ha ezeket külön elvárásként számolnánk, a CV
    olyat hiányolna, ami valójában benne van -- és az illeszkedési
    százalék alulmérne.
    """
    db = kliens()
    if not db or not keszseg_idk:
        return set()
    fogalmak: set[str] = set()
    idk = sorted(keszseg_idk)
    for kezdet in range(0, len(idk), 200):
        valasz = (
            db.table("keszsegek").select("id, nev, kanonikus, fogalom")
            .in_("id", idk[kezdet : kezdet + 200]).execute()
        )
        for sor in valasz.data or []:
            # Ha egy készséghez nincs gyűjtőfogalom, a saját neve áll helyette.
            jelolt = sor.get("fogalom") or sor.get("kanonikus") or sor.get("nev")
            if jelolt:
                fogalmak.add(normalizal(jelolt))
    return fogalmak


def _szakma_elvarasai(szakma_id: int | None, szakma: str) -> list[dict]:
    """Csak validált, teljes snapshotból származó elvárások.

    Nincs legacy nézetre vagy snippetből képzett készségre visszaesés:
    elégtelen hiteles adat esetén az ATS inkább nem számol százalékot.
    """

    del szakma  # a kompatibilis függvényaláírás része
    if not szakma_id:
        return []
    return _piaci_szures(
        szakma_elvarasai(szakma_id)[:FIGYELT_KESZSEGEK]
    )


def _piaci_szures(elvarasok: list[dict]) -> list[dict]:
    """Csak azt tartjuk meg, ami tényleg piaci elvárás.

    Ami a szakma hirdetéseinek töredékében szerepel, az egy adott
    munkáltató sajátossága -- azt nem hiányolhatjuk a CV-ből. Ha a
    küszöb mindent kiszűrne (kevés adat), a három leggyakoribb marad.
    """
    piaci = [e for e in elvarasok if e["szazalek"] >= PIACI_KUSZOB_SZAZALEK]
    return piaci or elvarasok[:3]


def ats_diagnozis(cv_szoveg: str, szakma: str) -> dict:
    """A CV és a szakma mért elvárásainak összevetése.

    Nulla modellhívás. Ugyanarra a CV-re mindig ugyanazt adja.
    """
    szakma_id = _szakma_id(szakma)
    keszsegek = _szakma_elvarasai(szakma_id, szakma)

    if not keszsegek:
        return {
            "illeszkedes_szazalek": 0,
            "van_eselye": True,
            "hianyzo_kulcsszavak": [],
            "meglevo_kulcsszavak": [],
            "fo_problema": "Még nincs elég készség-adat ehhez a szakmához.",
            "kepzes_kell": False,
        }

    hianyzo_mind = [
        {
            "szo": sor["nev"],
            "hirdetesek_szama": sor["elofordulas"],
            "fontos": sor["szazalek"] >= FONTOS_SZAZALEK,
        }
        for sor in keszsegek
    ]

    if not (cv_szoveg or "").strip():
        return {
            "illeszkedes_szazalek": 0,
            "van_eselye": False,
            "hianyzo_kulcsszavak": sorted(
                hianyzo_mind, key=lambda h: -h["hirdetesek_szama"]
            ),
            "meglevo_kulcsszavak": [],
            "fo_problema": "Nincs feltöltött CV, nincs mivel összevetni.",
            "kepzes_kell": False,
        }

    valtozatok = valtozatok_szakmahoz(szakma_id)
    megvan_fogalmak = _felismert_fogalmak(
        felismert_keszseg_idk(cv_szoveg, valtozatok)
    )

    # A munkáltatók megnevezései. Ha egyik sem szerepel a CV-ben, a HR-es
    # keresésénél a pályázat elő sem jön -- hiába megvan a tudás.
    bevett_nevek = pozicionevek(szakma_id)
    cvben_levo_nevek = cvben_szereplo(cv_szoveg, bevett_nevek)

    meglevo, hianyzo = [], []
    meglevo_suly = 0.0
    ossz_suly = 0.0
    for sor, leiras in zip(keszsegek, hianyzo_mind):
        # A súly a piaci gyakoriság: ami a hirdetések 44%-ában elvárás,
        # az négyszer annyit nyom, mint ami 11%-ában. Enélkül a „pult
        # kitörlése" ugyanannyit érne, mint a kasszakezelés.
        suly = max(sor["szazalek"], 0.1)
        ossz_suly += suly
        if normalizal(sor["nev"]) in megvan_fogalmak:
            meglevo.append(sor["nev"])
            meglevo_suly += suly
        else:
            hianyzo.append(leiras)

    szazalek = round(100 * meglevo_suly / ossz_suly) if ossz_suly else 0
    fontos_hianyzo = [h for h in hianyzo if h["fontos"]]

    # A hiányzó pozíciónév előbbre való a hiányzó készségnél: az egyezés
    # nélkül a CV el sem jut odáig, hogy a készségeket nézzék.
    if bevett_nevek and not cvben_levo_nevek:
        fo_problema = (
            f"A CV-ben nem szerepel egyik bevett megnevezés sem "
            f"(pl. „{bevett_nevek[0]['nev']}”), pedig a HR-esek ezekre keresnek."
        )
    elif not hianyzo:
        fo_problema = "A leggyakoribb elvárások megvannak a CV-ben."
    elif fontos_hianyzo:
        fo_problema = (
            f"A hirdetések többségében elvárt „{fontos_hianyzo[0]['szo']}” "
            "nem szerepel a CV-ben."
        )
    else:
        fo_problema = (
            f"{len(hianyzo)} gyakori elvárás nem szerepel a CV-ben."
        )

    return {
        "illeszkedes_szazalek": szazalek,
        "van_eselye": szazalek >= 40,
        "hianyzo_kulcsszavak": sorted(
            hianyzo, key=lambda h: -h["hirdetesek_szama"]
        ),
        "meglevo_kulcsszavak": meglevo,
        "fo_problema": fo_problema,
        "kepzes_kell": bool(fontos_hianyzo),
        "bevett_pozicionevek": bevett_nevek,
        "cvben_szereplo_pozicionevek": cvben_levo_nevek,
    }
