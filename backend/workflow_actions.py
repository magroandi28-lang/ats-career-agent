"""A karrierfolyamat műveleteinek végrehajtása.

A folyamat gerince: az állapotgép eldönti, hogy egy művelet az adott
állapotból egyáltalán indítható-e, ez a modul pedig lefuttatja a hozzá
tartozó modult és megmondja, milyen GPS-nyomot hagy maga után.

Vezérlési elv (docs/felhasznaloi-allapotgep.md 2./3. pont): az LLM sosem
hajt végre műveletet, csak javasol. Ide kizárólag kifejezett felhasználói
művelet érkezhet, és minden végrehajtás előtt a `next_state()` kapuján
kell átmennie.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
import datetime
from typing import Final
from uuid import uuid4

import re

from agents.karrier_ugynok import allasok_minosegi_kereses
from backend.cv_ats import ats_diagnozis
from backend.cv_review_service import CvReviewError, create_improved_cv
from backend.keszseg_felismero import normalizal
from backend.career_state_machine import CareerAction
from backend.cv_import_service import cv_import_get
from backend.gps_vocabulary import ellenorzott_esemeny, ellenorzott_snapshot
from backend.profile_service import confirmed_values
from utils.adatbazis import (
    kereslet_korkep,
    kliens,
    cv_illesztes,
    szakma_csomag,
    szakma_elvarasai,
)


# docs/felhasznaloi-allapotgep.md 7.: „Legfeljebb öt találat látható; ha
# csak kettő megfelelő, kettőt mutat." A korlát felső határ, nem kvóta.
MAX_TALALAT: Final = 5

# Formai ellenőrzéshez. Szándékosan megengedő minták: azt nézzük, van-e
# egyáltalán elérhetőség a dokumentumban, nem azt, hogy szabályos-e.
EMAIL_MINTA: Final = re.compile(r"[^\s@]+@[^\s@]+\.[A-Za-z]{2,}")
TELEFON_MINTA: Final = re.compile(r"(?:\+?\d[\d\s\-/()]{7,})")

# Életkorra utaló jelek. Ezek nem formai hibák, hanem kockázatok: az
# életkor alapján történő kiszűrés tiltott, mégis megtörténik, és a
# CV-ből egyszerűen elhagyható. A dátumot csak akkor jelezzük, ha
# tényleg születési dátumként szerepel, nem minden évszámot.
SZULETESI_DATUM_MINTA: Final = re.compile(
    r"szület(?:ési|ett)[^\n:]{0,20}:?\s*\d{4}", re.IGNORECASE
)

# Négyjegyű, 1940 és 2010 közötti szám az e-mail-cím helyi részében:
# jellemzően születési év (pl. nemeth.eva1975@…).
EMAIL_EVSZAM_MINTA: Final = re.compile(
    r"[^\s@]*(?:19[4-9]\d|200\d|2010)[^\s@]*@"
)

# A név a dokumentum elején áll; ennyi karakteren belül keressük.
NEV_SAV: Final = 300

# Ennél rövidebb darabot nem tekintünk névrésznek („dr", „hu", kezdőbetűk).
MIN_NEVRESZ: Final = 3

# A terjedelmet (a szakmai ajánlás 1,5-2 oldal) szándékosan NEM mérjük itt.
# A kinyert karakterszám nem arányos az oldalszámmal: egy tervezett, hasábos
# CV három oldal is lehet 2000 karakterrel. Ha ezt jelezni akarjuk, a PDF
# tényleges oldalszámát kell átadni a feltöltéskor, nem a szövegből becsülni.


class ActionError(RuntimeError):
    """A művelet nem hajtható végre; a szöveg a felhasználónak szól."""


class GpsNyomHiba(ValueError):
    """Hiányos GPS-nyom -- programozói hiba, nem felhasználói."""


@dataclass(frozen=True)
class ActionContext:
    """Minden, amit egy művelet a végrehajtáshoz megkaphat.

    A művelet szándékosan nem kap adatbázis-klienst és nem ír állapotot:
    az állapotmentés a hívó orchestrator (main.py) dolga.
    """

    user_id: str
    workflow: dict
    profile: dict
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ActionOutcome:
    """A művelet eredménye és az általa indokolt GPS-nyom."""

    result: dict
    gps_esemeny: str | None = None
    gps_terulet: str | None = None
    gps_allapot: str | None = None
    gps_payload: dict = field(default_factory=dict)
    context_patch: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.gps_esemeny is not None:
            ellenorzott_esemeny(self.gps_esemeny)
        if self.gps_terulet is not None or self.gps_allapot is not None:
            if not (self.gps_terulet and self.gps_allapot):
                raise GpsNyomHiba(
                    "A GPS-nyomhoz terület és állapot is kell."
                )
            ellenorzott_snapshot(self.gps_terulet, self.gps_allapot)


def _celmunkakor(ctx: ActionContext) -> str:
    """A megerősített célmunkakör; enélkül nincs mihez viszonyítani.

    Kizárólag megerősített profiladatból dolgozunk: a vázlat még nem tény
    (docs/felhasznaloi-allapotgep.md 5. elfogadási feltétel).
    """
    ertekek = confirmed_values(ctx.profile)
    szakma = str(ertekek.get("target_role") or "").strip()
    if not szakma:
        raise ActionError(
            "Ehhez a lépéshez előbb erősítsd meg a célmunkakörödet."
        )
    return szakma


def _piaci_korkep_inditasa(ctx: ActionContext) -> ActionOutcome:
    """Dátumozott, forrásolt piaci összevetés a saját adatbázisunkból.

    Nulla modellhívás: minden szám mért adat.

    A `szakma_csomag` RPC-ből dolgozik, nem a régi `szakma_statisztika`-ból.
    Ez három dolgot változtat:

    1. Nem a leállított `hirdetes_keszseg` táblából veszi az elvárásokat.
    2. Kérdésenként külön bizalmi szintet mutat (kereslet / bér / elvárás).
       Egyetlen közös jelző félrevezetne: egy szakmáról tudhatjuk pontosan,
       mennyi állás van, miközben a béréről semmit.
    3. Az átjárhatóság ingyen jön: a csomag `szomszedok` mezője megmondja,
       mely szakmákba vihető át a tudás. Ehhez eddig külön hívás kellett.

    A kereslet-trendet (30 napos ablakpár) továbbra is a `kereslet_korkep()`
    adja -- ez időbeli összehasonlítás, a csomag pedig pillanatkép.
    """
    szakma = _celmunkakor(ctx)
    csomag = szakma_csomag(szakma)
    korkep = kereslet_korkep()
    # MIT VARNAK EL -- a csomag ezt NEM adja vissza, csak a bizalmi szintjet.
    # Enelkul a korkep azt jelezte, hogy tudna valaszolni a kerdesre, kozben
    # nem irt ki semmit. Determinisztikus, modellhivas nelkul.
    elvarasok = szakma_elvarasai(szakma)
    sajat_kereslet = next(
        (sor for sor in korkep if sor["szakma"].casefold() == szakma.casefold()),
        None,
    )

    if not csomag and sajat_kereslet is None:
        raise ActionError(
            f"A(z) „{szakma}” szakmáról még nincs elég saját piaci adatunk."
        )

    lefedettseg = csomag.get("lefedettseg") or {}
    ber = csomag.get("ber") or {}

    return ActionOutcome(
        result={
            "szakma": csomag.get("szakma") or szakma,
            # Kérdésenkénti bizalom -- a felület ezt írja ki az adat mellé,
            # hogy a felhasználó lássa, mennyire állhat rajta.
            "bizalom": {
                "kereslet": lefedettseg.get("kereslet_bizalom"),
                "ber": lefedettseg.get("ber_bizalom"),
                "elvaras": lefedettseg.get("elvaras_bizalom"),
            },
            "hirdetesek_szama": lefedettseg.get("allas") or 0,
            "cegek_szama": lefedettseg.get("ceg") or 0,
            "teteles_hirdetes": lefedettseg.get("teteles") or 0,
            "kereslet": sajat_kereslet,
            "ber": {
                "hirdetett_median": ber.get("hirdetett_median"),
                "hirdetett_mintaszam": ber.get("hirdetett_mintaszam"),
                "ksh_atlagkereset": ber.get("ksh_atlagkereset"),
                "ksh_idoszak": ber.get("ksh_idoszak"),
                "figyelmeztetes": ber.get("figyelmeztetes"),
            },
            "esco": csomag.get("esco") or [],
            # A hirdetesekbol kinyert, gyakorisag szerint rangsorolt tetelek.
            # Minden tetel mellett ott a `hirdetes_db`: ami egyetlen
            # hirdetesbol jon, az nem piaci elvaras, hanem egy ceg szovege.
            "elvarasok": elvarasok.get("elvarasok") or [],
            "feladatok": elvarasok.get("feladatok") or [],
            "elvaras_forras_hirdetes": elvarasok.get("forras_hirdetes") or 0,
            "atjarhatosag": (csomag.get("szomszedok") or [])[:5],
            "frissesseg": csomag.get("frissesseg"),
            "osszehasonlitott_szakmak": len(korkep),
        },
        gps_esemeny="market_snapshot_ready",
        gps_terulet="piaci_kep",
        gps_allapot="betoltve",
        # Flow eddig csak annyit tudott, hogy a piaci körkép „betöltve" --
        # azt nem, hogy MI jött ki belőle. Így nem tudott beszélni róla, csak
        # felajánlani. Ez a rövid összefoglaló az, amit ténylegesen mérve
        # tudunk; Flow ezen kívül nem állíthat számot.
        context_patch={
            "piaci_kep_szakma": szakma,
            "eredmeny_piaci_korkep": {
                "szakma": csomag.get("szakma") or szakma,
                "hirdetes": lefedettseg.get("allas") or 0,
                "ceg": lefedettseg.get("ceg") or 0,
                "ber_median": ber.get("hirdetett_median"),
                "ber_mintaszam": ber.get("hirdetett_mintaszam"),
                "bizalom": {
                    "kereslet": lefedettseg.get("kereslet_bizalom"),
                    "ber": lefedettseg.get("ber_bizalom"),
                    "elvaras": lefedettseg.get("elvaras_bizalom"),
                },
                "atjarhatosag": [
                    sz.get("szakma")
                    for sz in (csomag.get("szomszedok") or [])[:5]
                ],
                "mikor": datetime.datetime.now(
                    datetime.timezone.utc).isoformat(),
            },
        },
    )


def _jovahagyott_cv_szoveg(ctx: ActionContext) -> str:
    """A felhasználó által átnézett és jóváhagyott CV-szöveg, ha van.

    Álláskereséshez a CV nem kötelező (a kapu a célmunkakört, készségeket
    és helyszínt kéri), de ha van jóváhagyott CV, az pontosítja a rangsort.
    Jóvá nem hagyott kivonatot sosem használunk fel.
    """
    dokumentum_id = confirmed_values(ctx.profile).get("cv_document_id")
    if not dokumentum_id:
        return ""
    behozott = cv_import_get(ctx.user_id, str(dokumentum_id))
    if not behozott or behozott.get("review_status") != "approved":
        return ""
    return behozott.get("extracted_text") or ""


def _shortlist_mentese(user_id: str, feltetelek: dict, allasok: list) -> str | None:
    """Szerveroldali munkapéldány a találatokról.

    Nem kényelmi cache: a következő lépésben azt kell tudnunk ellenőrizni,
    hogy a kiválasztott állás tényleg szerepelt-e az általunk ajánlott
    listán -- ezt a kliens állítására bízni nem lehet.
    """
    db = kliens()
    if not db:
        return None
    shortlist_id = str(uuid4())
    most = datetime.datetime.now(datetime.UTC).isoformat()
    try:
        db.schema("private").table("background_jobs").insert({
            "id": shortlist_id,
            "user_id": user_id,
            "job_type": "job_shortlist",
            "status": "succeeded",
            "input_ref": feltetelek,
            "result_ref": {"allasok": allasok, "talalatok_szama": len(allasok)},
            "attempt_count": 1,
            "started_at": most,
            "completed_at": most,
            "updated_at": most,
        }).execute()
        return shortlist_id
    except Exception as exc:
        print(f"[workflow_actions] shortlist-mentes hiba: {exc}")
        return None


def _keresesi_feltetelek(ctx: ActionContext) -> dict:
    """A rangsorolás bemenete kizárólag megerősített profiladatból áll.

    docs/felhasznaloi-allapotgep.md 7.: „A rangsor bemenete az igazolt
    profil, cél, korlátok és friss hirdetés."
    """
    ertekek = confirmed_values(ctx.profile)
    helyszin = str(ertekek.get("location") or "").strip()
    munkavegzes = str(ertekek.get("work_mode") or "").strip()
    if not helyszin and not munkavegzes:
        raise ActionError(
            "Add meg, hol keresel munkát, vagy hogy távmunkát szeretnél."
        )
    keszsegek = [
        str(elem).strip()
        for elem in (ertekek.get("skills") or [])
        if str(elem).strip()
    ]
    if not keszsegek:
        raise ActionError(
            "A rangsoroláshoz előbb erősítsd meg legalább egy készségedet."
        )
    return {
        "szakma": _celmunkakor(ctx),
        "helyszin": helyszin or munkavegzes,
        "keszsegek": keszsegek,
        "korlatok": ertekek.get("constraints") or [],
    }


def _allaskereses_inditasa(ctx: ActionContext) -> ActionOutcome:
    """Csak a keresési feltételeket zárja le, találatot még nem ad.

    A keresés indítása és az eredmény két külön lépés (7. pont): így a
    felhasználó látja, mivel fogunk keresni, mielőtt bármi lefutna.
    """
    feltetelek = _keresesi_feltetelek(ctx)
    return ActionOutcome(
        result={**feltetelek, "talalat_meg_nincs": True},
        gps_terulet="palyazas",
        gps_allapot="nincs_shortlist",
        context_patch={
            "kereses_szakma": feltetelek["szakma"],
            "kereses_helyszin": feltetelek["helyszin"],
        },
    )


def _allasok_bemutatasa(ctx: ActionContext) -> ActionOutcome:
    """Legfeljebb öt megfelelő találat, determinisztikus rangsorolással.

    A `szakma_info` szándékosan a megerősített profilból épül, nem
    `szakma_felismeres()` modellhívásból: így a rangsor bemenete igazolt
    tény, és egy modellhívással kevesebb történik.

    A shortlistet elmentjük, mert a következő lépés (állás kiválasztása)
    nem bízhat a kliens állításában arról, mit ajánlottunk neki.
    """
    feltetelek = _keresesi_feltetelek(ctx)
    cv_szoveg = _jovahagyott_cv_szoveg(ctx)

    talalat = allasok_minosegi_kereses(
        cv_szoveg,
        {
            "szakma": feltetelek["szakma"],
            "utos_kulcsszavak": feltetelek["keszsegek"],
            "ajanlott_cegek": [],
        },
        feltetelek["helyszin"],
    )
    allasok = (talalat.get("allasok") or [])[:MAX_TALALAT]
    shortlist_id = _shortlist_mentese(ctx.user_id, feltetelek, allasok)

    return ActionOutcome(
        result={
            "szakma": feltetelek["szakma"],
            "helyszin": feltetelek["helyszin"],
            "shortlist_id": shortlist_id,
            "allasok": allasok,
            "talalatok_szama": len(allasok),
            "forras": talalat.get("forras"),
            "piaci_jelzes": talalat.get("piaci_jelzes"),
        },
        gps_esemeny="job_shortlist_created",
        gps_terulet="palyazas",
        gps_allapot="shortlist" if allasok else "nincs_shortlist",
        gps_payload={"talalatok_szama": len(allasok)},
        context_patch={"shortlist_id": shortlist_id} if shortlist_id else {},
    )


def _email_tartalmazza_a_nevet(cv_szoveg: str) -> bool:
    """Az e-mail-cím elején szerepel-e a jelölt neve.

    A név a CV elején áll, a cím helyi részét pedig pontok, kötőjelek és
    számok tagolják. Ha a két halmaznak van közös eleme, a HR-es össze
    tudja kötni a levelet a pályázattal. A `cicamica88@` nem tudja.

    Nem ízlést mérünk: a név vagy szerepel benne, vagy nem.
    """
    talalat = EMAIL_MINTA.search(cv_szoveg)
    if not talalat:
        return True  # Az e-mail hiányát külön kifogás jelzi.

    helyi_resz = talalat.group(0).split("@")[0]
    # Betűhatáron darabolunk: a normalizálás a pontot és a kötőjelet már
    # szóközzé alakította, a számokat viszont meghagyta („eva1975").
    darabok = {
        darab for darab in re.split(r"[^a-z]+", normalizal(helyi_resz))
        if len(darab) >= MIN_NEVRESZ
    }
    if not darabok:
        return False

    # Magát az e-mail-címet ki kell venni a névsávból, különben a helyi rész
    # önmagára illeszkedik, és minden cím átmenne.
    nev_sav = normalizal(EMAIL_MINTA.sub(" ", cv_szoveg[:NEV_SAV]))
    return any(darab in nev_sav for darab in darabok)


def _formai_kifogasok(cv_szoveg: str) -> list[dict]:
    """Miért dobhatja ki a szűrő a dokumentumot, mielőtt bárki elolvasná.

    Tisztán determinisztikus: a kinyert szövegen mért jelek, nulla
    modellhívás. Nem a tartalmat nézi, hanem hogy a gép egyáltalán
    értelmesen ki tudja-e olvasni.
    """
    kifogasok: list[dict] = []
    sorok = [sor for sor in cv_szoveg.splitlines() if sor.strip()]

    if len(cv_szoveg) < 600:
        kifogasok.append({
            "kod": "keves_szoveg",
            "leiras": (
                "Nagyon kevés kiolvasható szöveg van a fájlban. Ez akkor "
                "fordul elő, ha a CV képként vagy szkennelve készült — a "
                "szűrőprogram ilyenkor gyakorlatilag üres lapot lát."
            ),
        })

    if not EMAIL_MINTA.search(cv_szoveg):
        kifogasok.append({
            "kod": "nincs_email",
            "leiras": (
                "Nem találtunk e-mail címet. A szűrőprogramok többsége "
                "elérhetőség nélkül nem tudja feldolgozni a jelentkezést."
            ),
        })

    if not TELEFON_MINTA.search(cv_szoveg):
        kifogasok.append({
            "kod": "nincs_telefon",
            "leiras": "Nem találtunk telefonszámot a dokumentumban.",
        })

    hosszu_sorok = sum(1 for sor in sorok if len(sor) > 200)
    if sorok and hosszu_sorok / len(sorok) > 0.15:
        kifogasok.append({
            "kod": "osszefolyo_sorok",
            "leiras": (
                "A szöveg sok helyen egyetlen hosszú sorba folyik össze. Ez "
                "jellemzően több hasábos vagy táblázatos elrendezésből "
                "adódik, amit a szűrőprogramok összekevernek."
            ),
        })

    if SZULETESI_DATUM_MINTA.search(cv_szoveg):
        kifogasok.append({
            "kod": "szuletesi_datum",
            "leiras": (
                "Szerepel a születési dátumod. Ezt nem kötelező megadni, és "
                "sajnos előfordul, hogy életkor alapján szűrnek ki jelölteket. "
                "Hagyd ki — az életkorod az interjún úgyis kiderül."
            ),
        })

    if not _email_tartalmazza_a_nevet(cv_szoveg):
        kifogasok.append({
            "kod": "email_becenev",
            "leiras": (
                "Az e-mail-címedben nem szerepel a neved. A HR-es így nehezen "
                "köti össze a levelet a pályázatoddal, és a becenevet gyakran "
                "komolytalannak látják. Egy név alapú cím sokat javít ezen."
            ),
        })

    if EMAIL_EVSZAM_MINTA.search(cv_szoveg):
        kifogasok.append({
            "kod": "email_evszam",
            "leiras": (
                "Az e-mail-címed évszámot tartalmaz, ami elárulhatja a "
                "születési évedet. Érdemes olyan címet használni a "
                "pályázatokhoz, amiből ez nem derül ki."
            ),
        })

    return kifogasok


def _cv_ellenorzes_inditasa(ctx: ActionContext) -> ActionOutcome:
    """CV-átvizsgálás két rétegben, konkrét álláshirdetés nélkül.

    1. Formai: miért dobhatja ki a szűrő a dokumentumot -- determinisztikus.
    2. Tartalmi: mely, a saját hirdetés-adatbázisunkban mért elvárások
       hiányoznak a CV-ből. A százalékot kód számolja a v_szakma_keszsegek
       nézetből, a készségfelismerést pedig szinonimaszótár végzi --
       egyik lépésben sincs modellhívás, tehát a vizsgálat ingyenes, és
       ugyanarra a CV-re mindig ugyanazt adja.

    Egyik réteghez sem kell hirdetés: az egész szakma piaci képe megvan az
    adatbázisban.
    """
    szakma = _celmunkakor(ctx)
    cv_szoveg = _jovahagyott_cv_szoveg(ctx)
    if not cv_szoveg:
        raise ActionError(
            "Az átvizsgáláshoz előbb töltsd fel és hagyd jóvá a CV-det."
        )

    formai = _formai_kifogasok(cv_szoveg)
    diagnozis = ats_diagnozis(cv_szoveg, szakma)
    hianyzo = diagnozis.get("hianyzo_kulcsszavak") or []

    # SZÓKINCS + EMLÉKEZTETŐ. A CV mondatait odaadjuk az ESCO-nak, és
    # visszakapjuk, hogy amit a felhasználó a maga szavaival leírt, annak mi a
    # szakmai megfogalmazása -- plusz a szakma teljes készséglistáját, amit
    # végig lehet kérdezni.
    #
    # Nulla modellhívás. Az átfogalmazás maga később modellel megy, de az
    # ALAP itt determinisztikus: az ESCO adja a szavakat, nem a modell.
    mondatok = [
        m.strip() for m in re.split(r"[\n•;]|(?<=[.!?])\s", cv_szoveg)
        if len(m.strip()) >= 8
    ][:60]
    # A 0,25-os küszöb kizárja az iparági különlegességeket. Mérve: a
    # „raktáros" 133 ESCO-készségéből 101 olyan foglalkozásból jön, ami a
    # szakmának csak egy szelete (bőrgyári, cipőgyári raktáros) -- egy
    # általános raktárosnak a kéregbőr tulajdonságait felajánlani zaj.
    illesztes = cv_illesztes(szakma, mondatok, min_mag=0.25)

    # Amire VAN bizonyíték a CV-ben: ezt csak jobban kell megfogalmazni.
    szokincs = [
        {"szakmai_megfogalmazas": s["keszseg"],
         "a_cv_ben_igy_all": s["cv_bizonyitek"],
         "kotelezo": s.get("kotelezo", False)}
        for s in illesztes if s.get("cv_bizonyitek")
    ]
    # Amire NINCS: ezt nem hiányként, hanem kérdésként adjuk tovább.
    emlekezteto = [
        {"keszseg": s["keszseg"], "kotelezo": s.get("kotelezo", False)}
        for s in illesztes if not s.get("cv_bizonyitek")
    ]

    return ActionOutcome(
        result={
            "szakma": szakma,
            "formai_kifogasok": formai,
            "illeszkedes_szazalek": diagnozis.get("illeszkedes_szazalek", 0),
            "hianyzo_elvarasok": hianyzo[:10],
            "meglevo_elvarasok": (diagnozis.get("meglevo_kulcsszavak") or [])[:10],
            "fo_problema": diagnozis.get("fo_problema", ""),
            "szokincs": szokincs[:15],
            "emlekezteto": emlekezteto[:20],
            "emlekezteto_ossz": len(emlekezteto),
        },
        gps_terulet="felkeszultseg",
        gps_allapot="megfelelo" if not formai and not hianyzo else "hianyok",
        context_patch={
            "cv_ellenorzes_szakma": szakma,
            "eredmeny_cv_ellenorzes": {
                "szakma": szakma,
                "illeszkedes_szazalek": diagnozis.get("illeszkedes_szazalek", 0),
                "formai_kifogas_db": len(formai),
                "hianyzo_elvaras": [
                    (h.get("szo") if isinstance(h, dict) else h)
                    for h in hianyzo[:5]
                ],
                "szokincs_db": len(szokincs),
                "emlekezteto_db": len(emlekezteto),
                "mikor": datetime.datetime.now(
                    datetime.timezone.utc).isoformat(),
            },
        },
    )


def _cv_uj_valtozat_inditasa(ctx: ActionContext) -> ActionOutcome:
    """A jóváhagyott CV-ből tényellenőrzött, szerkeszthető változatot készít."""
    szakma = _celmunkakor(ctx)
    cv_szoveg = _jovahagyott_cv_szoveg(ctx)
    if not cv_szoveg:
        raise ActionError(
            "Az átvizsgáláshoz előbb töltsd fel és hagyd jóvá a CV-det."
        )
    try:
        result = create_improved_cv(
            cv_szoveg,
            szakma,
            user_id=ctx.user_id,
        )
    except CvReviewError as exc:
        raise ActionError(str(exc)) from exc

    fact_check = result.get("fact_check") or {}
    basis = result.get("database_basis") or {}
    return ActionOutcome(
        result=result,
        gps_terulet="felkeszultseg",
        gps_allapot="terv",
        context_patch={
            "cv_ellenorzes_szakma": szakma,
            # AZ ÚJ CV SZÖVEGE MEGMARAD, KÜLÖNBEN NINCS MIT LETÖLTENI.
            #
            # Eddig csak az összefoglaló került a folyamat állapotába, a CV
            # maga pedig egyetlen válaszban élt: F5 után elveszett, és a
            # letöltéshez újra le kellett volna futtatni a teljes -- fizetős --
            # láncot. A DOCX/PDF ebből a szövegből készül, kéréskor.
            "cv_uj_valtozat": result.get("improved_cv") or "",
            "eredmeny_cv_ellenorzes": {
                "szakma": result.get("target_role") or szakma,
                "statusz": fact_check.get("status"),
                "igazolt_teny_db": fact_check.get("verified_fact_count") or 0,
                "javitott_allitas_db": len(
                    fact_check.get("corrected_claims") or []
                ),
                "esco_foglalkozas_db": (
                    basis.get("esco_occupations_considered") or 0
                ),
                "mikor": datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
            },
        },
    )


Handler = Callable[[ActionContext], ActionOutcome]

# A regiszterben szereplő műveletek hajthatók végre. Ami nincs benne, arra a
# végpont 501-et ad: az állapotgép ismeri az átmenetet, de a modul még nem
# készült el. Ez szándékosan megkülönböztethető a 409-től, ami azt jelenti,
# hogy a művelet ebből az állapotból nem is lenne szabad.
ACTION_HANDLERS: Final[dict[CareerAction, Handler]] = {
    CareerAction.PIACI_KORKEP_INDITASA: _piaci_korkep_inditasa,
    CareerAction.ALLASKERESES_INDITASA: _allaskereses_inditasa,
    CareerAction.ALLASOK_BEMUTATASA: _allasok_bemutatasa,
    CareerAction.CV_ELLENORZES_INDITASA: _cv_uj_valtozat_inditasa,
    CareerAction.CV_FRISSITES_INDITASA: _cv_uj_valtozat_inditasa,
}


def vegrehajthato(action: CareerAction) -> bool:
    return action in ACTION_HANDLERS


def execute_action(action: CareerAction, ctx: ActionContext) -> ActionOutcome:
    handler = ACTION_HANDLERS.get(action)
    if handler is None:
        raise NotImplementedError(f"Nincs végrehajtó a művelethez: {action}")
    return handler(ctx)
