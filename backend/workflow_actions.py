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

from agents.karrier_ugynok import (
    allasok_minosegi_kereses,
    ats_diagnozis_determinisztikus,
)
from backend.career_state_machine import CareerAction
from backend.cv_import_service import cv_import_get
from backend.gps_vocabulary import ellenorzott_esemeny, ellenorzott_snapshot
from backend.profile_service import confirmed_values
from utils.adatbazis import (
    kereslet_korkep,
    kliens,
    ksh_kereset,
    szakma_statisztika,
)


# docs/felhasznaloi-allapotgep.md 7.: „Legfeljebb öt találat látható; ha
# csak kettő megfelelő, kettőt mutat." A korlát felső határ, nem kvóta.
MAX_TALALAT: Final = 5

# Formai ellenőrzéshez. Szándékosan megengedő minták: azt nézzük, van-e
# egyáltalán elérhetőség a dokumentumban, nem azt, hogy szabályos-e.
EMAIL_MINTA: Final = re.compile(r"[^\s@]+@[^\s@]+\.[A-Za-z]{2,}")
TELEFON_MINTA: Final = re.compile(r"(?:\+?\d[\d\s\-/()]{7,})")


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

    Nulla modellhívás: a hirdetésszám, a készséggyakoriság és a bérsávok
    mind mért adatok. A KSH-átlagkereset csak akkor kerül bele, ha a
    foglalkozásnév ténylegesen illeszkedik -- becslést nem gyártunk.
    """
    szakma = _celmunkakor(ctx)
    statisztika = szakma_statisztika(szakma)
    korkep = kereslet_korkep()
    sajat_kereslet = next(
        (sor for sor in korkep if sor["szakma"].casefold() == szakma.casefold()),
        None,
    )

    if not statisztika and sajat_kereslet is None:
        raise ActionError(
            f"A(z) „{szakma}” szakmáról még nincs elég saját piaci adatunk."
        )

    return ActionOutcome(
        result={
            "szakma": szakma,
            "kereslet": sajat_kereslet,
            "hirdetesek_szama": statisztika.get("hirdetesek_szama", 0),
            "keszsegek": (statisztika.get("keszsegek") or [])[:10],
            "bersavok": (statisztika.get("bersavok") or [])[:5],
            "ksh_atlagkereset": ksh_kereset(szakma),
            "osszehasonlitott_szakmak": len(korkep),
        },
        gps_esemeny="market_snapshot_ready",
        gps_terulet="piaci_kep",
        gps_allapot="betoltve",
        context_patch={"piaci_kep_szakma": szakma},
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

    return kifogasok


def _cv_ellenorzes_inditasa(ctx: ActionContext) -> ActionOutcome:
    """CV-átvizsgálás két rétegben, konkrét álláshirdetés nélkül.

    1. Formai: miért dobhatja ki a szűrő a dokumentumot -- determinisztikus.
    2. Tartalmi: mely, a saját hirdetés-adatbázisunkban mért elvárások
       hiányoznak a CV-ből. A százalékot kód számolja a v_szakma_keszsegek
       nézetből, nem modell.

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
    diagnozis = ats_diagnozis_determinisztikus(cv_szoveg, {"szakma": szakma})
    hianyzo = diagnozis.get("hianyzo_kulcsszavak") or []

    return ActionOutcome(
        result={
            "szakma": szakma,
            "formai_kifogasok": formai,
            "illeszkedes_szazalek": diagnozis.get("illeszkedes_szazalek", 0),
            "hianyzo_elvarasok": hianyzo[:10],
            "meglevo_elvarasok": (diagnozis.get("meglevo_kulcsszavak") or [])[:10],
            "fo_problema": diagnozis.get("fo_problema", ""),
        },
        gps_terulet="felkeszultseg",
        gps_allapot="megfelelo" if not formai and not hianyzo else "hianyok",
        context_patch={"cv_ellenorzes_szakma": szakma},
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
    CareerAction.CV_ELLENORZES_INDITASA: _cv_ellenorzes_inditasa,
}


def vegrehajthato(action: CareerAction) -> bool:
    return action in ACTION_HANDLERS


def execute_action(action: CareerAction, ctx: ActionContext) -> ActionOutcome:
    handler = ACTION_HANDLERS.get(action)
    if handler is None:
        raise NotImplementedError(f"Nincs végrehajtó a művelethez: {action}")
    return handler(ctx)
