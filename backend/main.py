"""
FastAPI backend vaz -- Karrier-Ugynokseg

Ez meg NEM tartalmazza a meglevo logikat (CV-elemzes, piaci adatok, Flow stb.) --
csak azt bizonyitja, hogy a szerver elindul es valaszol. A regi Streamlit app
(app.py) ettol fuggetlenul, zavartalanul tovabb fut.

Kovetkezo lepes: ide kerulnek majd a valodi vegpontok, az agents/ es utils/
mappak meglevo fuggvenyei korul kiepitve.

Inditas (a projekt gyokerebol):
    uvicorn backend.main:app --reload

Utana a bongeszoben:
    http://localhost:8000/healthz   -> egyszeru elet-jel
    http://localhost:8000/docs      -> automatikus, kattintgathato API-dokumentacio
"""

from typing import Literal

from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from agents.karrier_ugynok import (
    szakma_felismeres,
    allasok_minosegi_kereses,
    ats_diagnozis_determinisztikus,
    cv_atiras,
    motivacios_level,
    kepzes_ajanlat,
    ceginfo_kereses,
    skill_gap_elemzes,
    tanacsado_velemeny,
)
from utils.adatbazis import kereslet_korkep, szakma_statisztika, kliens
from utils.teszt import ENERGIA_SKALA, STRESSZ_SKALA, holland_tipus, jollet_jelzes
from utils.flow_agy import flow_kiertekeles, flow_dontes, flow_vendeg_valasz
from utils.flow_allapot import (
    session_lekeres_vagy_letrehozas,
    elozmenyek_lekerese,
    uzenet_mentese,
    workflow_lekeres_vagy_letrehozas,
    workflow_frissites,
    workflow_ujrakezdes,
    gps_esemeny_rogzitese,
    gps_snapshot_frissites,
    gps_projekcio,
)
from backend.career_state_machine import (
    CareerAction,
    CareerIntent,
    CareerState,
    allowed_actions,
    confirm_intent_transition,
    next_state,
)
from backend.profile_service import (
    ALLOWED_FIELDS,
    profile_confirm,
    profile_get_or_create,
    profile_readiness,
    profile_update_draft,
)
from backend.cv_import_service import (
    cv_import_create,
    cv_import_get,
    cv_import_mark_approved,
)
from backend.workflow_actions import (
    ActionContext,
    ActionError,
    execute_action,
    vegrehajthato,
)
from backend.auth import (
    auth_keres_limit,
    friss_auth_kliens,
    jelenlegi_felhasznalo,
)
from backend.security import (
    RequestSecurityMiddleware,
    limit_guest_ai_request,
    read_validated_pdf,
)
from backend.settings import get_settings

settings = get_settings()
app = FastAPI(
    title="Karrier-Ugynokseg API",
    docs_url=None if settings.production else "/docs",
    redoc_url=None if settings.production else "/redoc",
    openapi_url=None if settings.production else "/openapi.json",
)

# Enged: a Vercelen elo React/Next.js oldal (es a helyi fejlesztoi szerver is)
# hivhassa ezt a backendet a bongeszobol. CORS nelkul a bongeszo blokkolna
# a valaszt, meg akkor is, ha a szerver maga rendesen valaszolt.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "X-Request-ID",
    ],
    expose_headers=["X-Request-ID"],
    allow_credentials=False,
)
app.add_middleware(RequestSecurityMiddleware)


@app.get("/health/live")
def health_live():
    """Folyamat-életjelet ad, külső szolgáltatást nem érint."""
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready():
    """Csak akkor jelez kész állapotot, ha az alapkapcsolatok konfiguráltak."""
    if not settings.auth_ready or not settings.database_ready:
        raise HTTPException(503, "A szolgáltatás még nem áll készen.")
    return {"status": "ready"}


@app.get("/healthz")
def healthz():
    """
    Ezt fogja majd pingelni a GitHub Actions 10-14 percenkent, hogy a Render
    ingyenes szolgaltatasa ne aludjon el.
    """
    return {"status": "ok", "uzenet": "Elek!"}


class ApiModel(BaseModel):
    """Minden API-bemenetnél tiltja a nem dokumentált mezőket."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SzakmaFelismeresBemenet(ApiModel):
    """Ez irja le, MIT varunk a keresben. A FastAPI ez alapjan automatikusan
    ellenorzi es Python-objektumma alakitja a bejovo adatot -- ezt hivjak
    'Pydantic modell'-nek."""
    cv_szoveg: str = Field(default="", max_length=120_000)
    szakma_megadva: str = Field(default="", max_length=200)


@app.post("/szakma-felismeres")
def szakma_felismeres_vegpont(
    bemenet: SzakmaFelismeresBemenet,
    _felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """
    Az ELSO valodi vegpont. A mar meglevo szakma_felismeres() fuggvenyt hivja
    (agents/karrier_ugynok.py) -- nem masolt vagy atirt kod, ugyanaz a logika,
    csak mostantol HTTP-n keresztul is elerheto, nem csak a Streamlit app-bol.

    FONTOS: ez a fuggveny valodi OpenAI-hivast tesz (par filleres koltseg).
    Ezert ezt a vegpontot NEM hivtuk meg automatikus tesztkent -- csak a
    strukturajat (regisztralt-e helyesen) ellenoriztuk.
    """
    return szakma_felismeres(bemenet.cv_szoveg, bemenet.szakma_megadva)


class AllasokBemenet(ApiModel):
    """A /szakma-felismeres valasza (szakma_info) megy ide vissza -- igy nem
    kell ujra kitalalni a szakmat, csak folytatjuk a lancot."""
    cv_szoveg: str = Field(default="", max_length=120_000)
    szakma_info: dict
    helyszin: str = Field(default="Budapest", max_length=200)


@app.post("/allasok")
def allasok_vegpont(
    bemenet: AllasokBemenet,
    _felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """
    Minoseg-elso allaskereses + rangsorolas. A teljes dontesi logika (80%-os
    kuszob, mikor megy ki a netre, mi tortenik ha meg ugy sincs jo talalat)
    az agents/karrier_ugynok.py allasok_minosegi_kereses()-ben van
    dokumentalva -- itt csak meghivjuk.
    """
    return allasok_minosegi_kereses(
        bemenet.cv_szoveg, bemenet.szakma_info, bemenet.helyszin
    )


class AtsBemenet(ApiModel):
    """Ugyanaz a szakma_info megy ide, mint az /allasok-ba -- a lanc
    harmadik lepese."""
    cv_szoveg: str = Field(default="", max_length=120_000)
    szakma_info: dict


@app.post("/ats-diagnozis")
def ats_diagnozis_vegpont(
    bemenet: AtsBemenet,
    _felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """
    Determinisztikus ATS-diagnozis: a szazalekot es a hianyzo kulcsszavak
    darabszamat KOD szamolja, valos adatbazis-adatokbol (v_szakma_keszsegek
    nezet) -- nem AI-becsles. Az AI szerepe csak annyi, hogy eldontse, a CV
    (akar pongyola megfogalmazasban) tartalmazza-e az adott keszseget.
    Reszletek: agents/karrier_ugynok.py, ats_diagnozis_determinisztikus().

    FONTOS: ha van cv_szoveg, ez a vegpont valodi OpenAI-hivast tesz (par
    filleres koltseg, gpt-5.6-luna, rovid prompt). Ures cv_szoveg-gel
    ingyenes, csak az adatbazist kerdezi le.
    """
    return ats_diagnozis_determinisztikus(bemenet.cv_szoveg, bemenet.szakma_info)


class CvAtirasBemenet(ApiModel):
    """A lanc negyedik lepese: az /allasok egyik talalata (allas) + a
    /ats-diagnozis eredmenye (diagnozis) alapjan irja at a CV-t."""
    cv_szoveg: str = Field(default="", max_length=120_000)
    allas: dict
    szakma_info: dict
    diagnozis: dict = Field(default_factory=dict)
    ceginfo: dict = Field(default_factory=dict)
    kiegeszites: str = Field(default="", max_length=10_000)


@app.post("/cv-atiras")
def cv_atiras_vegpont(
    bemenet: CvAtirasBemenet,
    _felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """
    CV-atiras egy konkret allashirdetesre szabva: beepiti az ATS-diagnozisbol
    hianyzo kulcsszavakat, termeszetes megfogalmazasban. Ez VALODI iras-feladat
    (nem pontszamitas) -- itt az AI-hasznalat indokolt, nem valtjuk ki.

    FONTOS: mindig valodi OpenAI-hivast tesz (a MINOSEGI modellel, tehat a
    dragabb tierrel -- ez a leghosszabb, legigenyesebb szoveges feladat az
    egesz alkalmazasban). Csak akkor hivd, ha tenyleg CV-szoveget akarsz kapni.
    """
    return {
        "cv_szoveg": cv_atiras(
            bemenet.cv_szoveg, bemenet.allas, bemenet.szakma_info,
            bemenet.diagnozis, bemenet.ceginfo, bemenet.kiegeszites,
        )
    }


class MotivaciosLevelBemenet(ApiModel):
    """Ugyanaz a bemenet-forma, mint a /cv-atiras-nal, csak diagnozis
    nelkul -- a motivacios level nem az ATS-hianyokra epul, hanem
    kozvetlenul az allasra es a cegre."""
    cv_szoveg: str = Field(default="", max_length=120_000)
    allas: dict
    szakma_info: dict
    ceginfo: dict = Field(default_factory=dict)
    kiegeszites: str = Field(default="", max_length=10_000)


@app.post("/motivacios-level")
def motivacios_level_vegpont(
    bemenet: MotivaciosLevelBemenet,
    _felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """
    Motivacios level egy konkret allashirdetesre es cegre szabva. Valodi
    iras-feladat (nem pontszamitas) -- az AI-hasznalat itt indokolt.

    FONTOS: mindig valodi OpenAI-hivast tesz (MINOSEGI modell). Csak akkor
    hivd, ha tenyleg szoveget akarsz kapni.
    """
    return {
        "level_szoveg": motivacios_level(
            bemenet.cv_szoveg, bemenet.allas, bemenet.szakma_info,
            bemenet.ceginfo, bemenet.kiegeszites,
        )
    }


class KepzesBemenet(ApiModel):
    """A /ats-diagnozis hianyzo_kulcsszavak listaja mehet ide hianyok-kent --
    igy a kepzes-ajanlas ugyanarra a hianyra epul, amit a diagnozis talalt."""
    szakma: str = Field(max_length=200)
    hianyok: list = Field(default_factory=list)
    szakma_kategoria: str = Field(default="", max_length=200)


@app.post("/kepzes-ajanlat")
def kepzes_ajanlat_vegpont(
    bemenet: KepzesBemenet,
    _felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """
    Kurált, kézzel karbantartott képzési adatbázisból válogat -- NINCS
    AI-hívás, NINCS internetes keresés, 0 forint, azonnali válasz.
    (agents/kepzes_db.py -- ezt kell majd élő gyűjtésre bővíteni, lásd a
    külön nyilvántartott feladatot.)
    """
    return {"kepzesek": kepzes_ajanlat(
        bemenet.szakma, bemenet.hianyok, bemenet.szakma_kategoria
    )}


# ── PIACI KÖRKÉP ──────────────────────────────────────────────

@app.get("/piaci-korkep")
def piaci_korkep_vegpont(
    _felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """
    Élő kereslet-mutató MINDEN szakmára: két 30 napos ablakot hasonlít
    össze (friss_30 vs elozo_30) -- 0 AI-hívás, csak Supabase-lekérdezés.
    """
    return {"szakmak": kereslet_korkep()}


class SzakmaStatBemenet(ApiModel):
    szakma: str = Field(max_length=200)


@app.post("/szakma-statisztika")
def szakma_statisztika_vegpont(
    bemenet: SzakmaStatBemenet,
    _felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """
    Egy konkrét szakma piaci képe: hirdetésszám, leggyakoribb elvárások
    (a v_szakma_keszsegek nézetből, százalékkal), bérinfók. 0 AI-hívás.
    """
    return szakma_statisztika(bemenet.szakma)


# ── TANÁCSADÓ TESZT (Holland + karrierhorgony + jóllét) ──────

class TanacsadoTesztBemenet(ApiModel):
    """h_pontok: {'R':1-4, 'I':1-4, 'A':1-4, 'S':1-4, 'E':1-4, 'C':1-4}
    (lásd utils/teszt.py HOLLAND_KERDESEK -- a kódok jelentése ott van).
    energia/stressz: PONTOSAN az ENERGIA_SKALA/STRESSZ_SKALA egyik szövege."""
    h_pontok: dict
    horgony1: str = Field(max_length=200)
    horgony2: str = Field(default="", max_length=200)
    energia: str = Field(max_length=200)
    stressz: str = Field(max_length=200)
    valtas_ok: str = Field(max_length=2_000)


@app.post("/tanacsado-teszt")
def tanacsado_teszt_vegpont(
    bemenet: TanacsadoTesztBemenet,
    _felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """
    A teszt PONTOZÁSA -- teljesen determinisztikus, 0 AI-hívás (Andi elve:
    a pontozás mindig kód, sosem AI). A szöveges kiértékeléshez lásd a
    /flow-kiertekeles végpontot, ami MÁR valódi AI-hívás.
    """
    tipus = holland_tipus(bemenet.h_pontok)
    jollet = jollet_jelzes(
        ENERGIA_SKALA.index(bemenet.energia),
        STRESSZ_SKALA.index(bemenet.stressz),
        bemenet.valtas_ok,
    )
    horgony_szoveg = bemenet.horgony1 + (
        f" · {bemenet.horgony2}" if bemenet.horgony2 else ""
    )
    return {"tipus": tipus, "horgony_szoveg": horgony_szoveg, "jollet": jollet}


# ── FLOW (mentálhigiénés kísérő) ──────────────────────────────

class FlowKiertekelesBemenet(ApiModel):
    """profil: a felhasznalo eddigi adatai (szakma, keszsegek, holland_tipus,
    karrierhorgony, jollet_jelzes stb.) -- a backend NEM tárol session-t,
    a hívó fél (frontend) adja át mindig a teljes profilt."""
    profil: dict


@app.post("/flow-kiertekeles")
def flow_kiertekeles_vegpont(
    bemenet: FlowKiertekelesBemenet,
    _felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """
    Flow részletes, személyre szabott kiértékelése a teszt + profil alapján.
    VALÓDI Gemini-hívás (jelenleg ingyenes egyetemi kerettel, aug. végéig).
    Üres profillal NEM hív API-t (lásd flow_agy.py: 'if not profil: return').
    """
    return {"kiertekeles": flow_kiertekeles(bemenet.profil)}


class FlowUzenetBemenet(ApiModel):
    """A /flow-chat utódja: nincs 'elozmenyek' mező, mert a backend saját
    maga tárolja és olvassa vissza a beszélgetést (private.flow_messages) --
    nem a kliens állítása szerint dolgozik."""
    kerdes: str = Field(max_length=8_000)
    # Átmeneti kompatibilitási mező: a backend szándékosan figyelmen kívül
    # hagyja. Személyre szabáshoz csak a szerveroldali, megerősített profil jó.
    profil: dict = Field(default_factory=dict)
    app_ismeret: str = Field(default="", max_length=20_000)


class WorkflowIntentBemenet(ApiModel):
    """Kifejezett felhasználói gombválasztás, LLM-értelmezés nélkül."""

    intent: CareerIntent


@app.post("/api/v1/workflow/reset")
def workflow_reset_vegpont(
    felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """Kifejezett visszalépés: a szerveroldali folyamatot is újrakezdi."""

    user_id = str(felhasznalo.id)
    session_id = session_lekeres_vagy_letrehozas(user_id)
    workflow = workflow_lekeres_vagy_letrehozas(user_id, session_id)
    if not workflow:
        raise HTTPException(503, "A karrierfolyamat állapota nem érhető el.")
    try:
        previous_state = CareerState(workflow["current_state"])
    except (KeyError, ValueError):
        raise HTTPException(500, "A karrierfolyamat állapota érvénytelen.")

    if not workflow_ujrakezdes(user_id, workflow["id"]):
        raise HTTPException(503, "A karrierfolyamat újrakezdése nem sikerült.")
    return {
        "ok": True,
        "previous_state": previous_state.value,
        "current_state": CareerState.CEL_TISZTAZATLAN.value,
    }


@app.post("/api/v1/workflow/intent")
def workflow_intent_vegpont(
    bemenet: WorkflowIntentBemenet,
    felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """Korai folyamatban determinisztikusan rögzíti a felhasználó célját.

    A frontend fix műveletgombjaihoz nem kell modellhívás: a kiválasztott
    intent közvetlenül, auditálhatóan kerül az állapotgépbe.
    """
    if bemenet.intent is CareerIntent.BIZONYTALAN:
        raise HTTPException(422, "Bizonytalan cél nem választható műveletgombbal.")

    user_id = str(felhasznalo.id)
    session_id = session_lekeres_vagy_letrehozas(user_id)
    workflow = workflow_lekeres_vagy_letrehozas(user_id, session_id)
    if not workflow:
        raise HTTPException(503, "A karrierfolyamat állapota nem érhető el.")

    try:
        previous_state = CareerState(workflow["current_state"])
    except (KeyError, ValueError):
        raise HTTPException(500, "A karrierfolyamat állapota érvénytelen.")

    profile = profile_get_or_create(user_id)
    if not profile:
        raise HTTPException(503, "A karrierprofil nem érhető el.")
    readiness = profile_readiness(bemenet.intent, profile)
    target_state = (
        CareerState.PROFIL_ELLENORZOTT
        if readiness["ready"]
        else CareerState.PROFIL_HIANYOS
    )

    context = dict(workflow.get("context") or {})
    context["intent_source"] = "explicit_ui_selection"
    context["profile_rule_version"] = readiness["rule_version"]
    if not workflow_frissites(
        user_id,
        workflow["id"],
        target_state,
        bemenet.intent,
        context,
    ):
        raise HTTPException(503, "A cél mentése nem sikerült.")

    event_id = gps_esemeny_rogzitese(
        user_id,
        session_id,
        "career_goal_selected",
        {
            "intent": bemenet.intent.value,
            "source": "explicit_ui_selection",
            "previous_state": previous_state.value,
            "current_state": target_state.value,
            "profile_ready": readiness["ready"],
        },
        actor="user",
    )
    gps_snapshot_frissites(
        user_id,
        "karriercel",
        "kivalasztott",
        event_id,
    )

    return {
        **_akcio_lista(target_state),
        "ok": True,
        "intent": bemenet.intent.value,
        "previous_state": previous_state.value,
        "current_state": target_state.value,
        "readiness": readiness,
        "model_called": False,
    }


class WorkflowActionBemenet(ApiModel):
    """Kifejezett felhasználói művelet, LLM-javaslat nélkül."""

    action: CareerAction
    payload: dict = Field(default_factory=dict)


@app.post("/api/v1/workflow/action")
def workflow_action_vegpont(
    bemenet: WorkflowActionBemenet,
    felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """A folyamat előreléptetése: kapu, végrehajtás, GPS-nyom, mentés.

    A sorrend nem cserélhető fel. Előbb az állapotgép dönti el, hogy a
    művelet ebből az állapotból egyáltalán indítható-e; csak utána fut le a
    modul; és csak sikeres futás után változik az állapot. Így egy elhasalt
    modul nem tud félkész állapotot hagyni a folyamatban.
    """
    user_id = str(felhasznalo.id)
    session_id = session_lekeres_vagy_letrehozas(user_id)
    workflow = workflow_lekeres_vagy_letrehozas(user_id, session_id)
    if not workflow:
        raise HTTPException(503, "A karrierfolyamat állapota nem érhető el.")
    try:
        previous_state = CareerState(workflow["current_state"])
    except (KeyError, ValueError):
        raise HTTPException(500, "A karrierfolyamat állapota érvénytelen.")

    if not workflow.get("intent"):
        raise HTTPException(409, "Előbb válaszd ki, mi a célod.")
    try:
        intent = CareerIntent(workflow["intent"])
    except ValueError:
        raise HTTPException(500, "A folyamat célja érvénytelen.")

    target_state = next_state(previous_state, bemenet.action)
    if target_state is None:
        raise HTTPException(
            409, "Ez a lépés a folyamat jelenlegi állapotából nem indítható."
        )
    if not vegrehajthato(bemenet.action):
        raise HTTPException(
            501, "Ez a lépés még nem érhető el. Dolgozunk rajta."
        )

    profile = profile_get_or_create(user_id)
    if not profile:
        raise HTTPException(503, "A karrierprofil nem érhető el.")

    try:
        outcome = execute_action(
            bemenet.action,
            ActionContext(
                user_id=user_id,
                workflow=workflow,
                profile=profile,
                payload=bemenet.payload,
            ),
        )
    except ActionError as exc:
        raise HTTPException(422, str(exc))

    context = dict(workflow.get("context") or {})
    context.update(outcome.context_patch)
    if not workflow_frissites(
        user_id, workflow["id"], target_state, intent, context
    ):
        raise HTTPException(503, "Az állapotváltás mentése nem sikerült.")

    event_id = None
    if outcome.gps_esemeny:
        event_id = gps_esemeny_rogzitese(
            user_id,
            session_id,
            outcome.gps_esemeny,
            {
                "action": bemenet.action.value,
                "previous_state": previous_state.value,
                "current_state": target_state.value,
                **outcome.gps_payload,
            },
            actor="user",
        )
    # A területjelzés eseménynapló nélkül is érvényes: van olyan lépés, ami
    # a folyamat állását változtatja, de nem keletkezik hozzá önálló,
    # auditálandó domain-esemény (utolso_esemeny_id nullable).
    if outcome.gps_terulet:
        gps_snapshot_frissites(
            user_id, outcome.gps_terulet, outcome.gps_allapot, event_id
        )

    return {
        **_akcio_lista(target_state),
        "ok": True,
        "action": bemenet.action.value,
        "previous_state": previous_state.value,
        "current_state": target_state.value,
        "state_changed": target_state != previous_state,
        "result": outcome.result,
    }


class FlowVendegElozmeny(ApiModel):
    """Egy korábbi üzenet a vendég-beszélgetésből."""

    szerep: Literal["user", "flow"]
    szoveg: str = Field(min_length=1, max_length=600)


class FlowVendegUzenetBemenet(ApiModel):
    """Vendégmódú (be nem jelentkezett) Flow-csevegés bemenete.

    Az előzményt itt a kliens küldi, mert vendégmódban szándékosan nincs
    szerveroldali tárolás. Ezért szűk a keret: legfeljebb 6 üzenet,
    darabonként 600 karakter -- és a prompt a beszélgetést adatként
    kezeli, nem utasításként.
    """

    kerdes: str = Field(min_length=1, max_length=600)
    elozmenyek: list[FlowVendegElozmeny] = Field(
        default_factory=list, max_length=6
    )


VENDEG_ALAPERTELMEZETT_VALASZ = (
    "Most nem érem el a válaszhoz szükséges szolgáltatást. Próbáld újra "
    "kicsit később, vagy lépj be, és onnan folytatjuk."
)


@app.post("/api/v1/flow/guest-messages")
def flow_vendeg_uzenet_vegpont(
    bemenet: FlowVendegUzenetBemenet,
    request: Request,
):
    """Vendégmódú Flow: szűk hatókör, nincs profil, nincs előzménymentés.

    Ez NEM a bejelentkezett Flow (/api/v1/flow/messages): nincs mögötte
    állapotgép, nem ír adatbázist, és nem ad személyre szabott tanácsot.
    Bejelentkezés nélkül hívható, ezért IP-alapú korlát védi.
    """
    limit_guest_ai_request(request)
    valasz = flow_vendeg_valasz(
        bemenet.kerdes,
        [
            {"szerep": sor.szerep, "szoveg": sor.szoveg}
            for sor in bemenet.elozmenyek
        ],
    )
    return {"valasz": valasz or VENDEG_ALAPERTELMEZETT_VALASZ}


@app.post("/api/v1/flow/messages")
def flow_uzenet_vegpont(
    bemenet: FlowUzenetBemenet,
    felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """
    Flow csak szándékot és következő műveletet javasol. A backend a
    szerveroldali állapotgéppel ellenőrzi, hogy a javaslat megengedett-e.
    CV-feltöltésből ezért nem indul automatikusan álláskeresés vagy ATS.
    """
    user_id = str(felhasznalo.id)
    session_id = session_lekeres_vagy_letrehozas(user_id)
    workflow = workflow_lekeres_vagy_letrehozas(user_id, session_id)
    if not workflow:
        raise HTTPException(503, "A karrierfolyamat állapota nem érhető el.")
    try:
        previous_state = CareerState(workflow["current_state"])
    except (KeyError, ValueError):
        raise HTTPException(500, "A karrierfolyamat állapota érvénytelen.")
    elozmenyek = elozmenyek_lekerese(user_id, session_id)
    profile = profile_get_or_create(user_id)
    if not profile:
        raise HTTPException(503, "A karrierprofil nem érhető el.")
    server_profile = dict(profile.get("confirmed_data") or {})

    uzenet_mentese(user_id, session_id, "user", bemenet.kerdes)

    dontes = flow_dontes(
        bemenet.kerdes,
        server_profile,
        bemenet.app_ismeret,
        elozmenyek,
        current_state=previous_state,
    )

    uzenet_mentese(
        user_id, session_id, "flow", dontes.response_message, dontes.evidence_refs,
    )

    current_state = previous_state
    accepted_action = None
    gps_esemeny = None
    if (
        dontes.intent is not CareerIntent.BIZONYTALAN
        and dontes.proposed_action is CareerAction.CEL_MEGEROSITESE
    ):
        next_workflow_state = confirm_intent_transition(
            previous_state, dontes.intent
        )
        if next_workflow_state is not None:
            context = dict(workflow.get("context") or {})
            if dontes.szakma:
                context["target_role"] = dontes.szakma
            if not workflow_frissites(
                user_id,
                workflow["id"],
                next_workflow_state,
                dontes.intent,
                context,
            ):
                raise HTTPException(503, "Az állapotváltás mentése nem sikerült.")
            current_state = next_workflow_state
            accepted_action = CareerAction.CEL_MEGEROSITESE

            esemeny_id = gps_esemeny_rogzitese(
                user_id,
                session_id,
                "career_intent_confirmed",
                {
                    "intent": dontes.intent.value,
                    "previous_state": previous_state.value,
                    "current_state": current_state.value,
                    "target_role": dontes.szakma or None,
                },
                actor="system",
            )
            gps_snapshot_frissites(
                user_id, "karriercel", "kivalasztott", esemeny_id
            )
            gps_esemeny = {
                "tipus": "career_intent_confirmed",
                "intent": dontes.intent.value,
            }
    elif dontes.intent is CareerIntent.BIZONYTALAN:
        accepted_action = CareerAction.TISZTAZO_KERDES

    proposed_action = dontes.proposed_action
    if proposed_action not in allowed_actions(previous_state):
        proposed_action = None

    return {
        "workflow_id": workflow["id"],
        "intent": dontes.intent.value,
        "response_message": dontes.response_message,
        "proposed_action": proposed_action.value if proposed_action else None,
        "accepted_action": accepted_action.value if accepted_action else None,
        "required_fields": dontes.required_fields,
        "specialist_request": dontes.specialist_request,
        "confidence": dontes.confidence,
        "szakma": dontes.szakma,
        "previous_state": previous_state.value,
        "current_state": current_state.value,
        "state_changed": current_state != previous_state,
        "allowed_actions": [
            action.value for action in allowed_actions(current_state)
        ],
        "gps_esemeny": gps_esemeny,
    }


class ProfileDraftPatchBemenet(ApiModel):
    fields: dict


class ProfileConfirmBemenet(ApiModel):
    fields: list[str] = Field(min_length=1, max_length=30)
    reason: str = Field(default="user_confirmation", min_length=1, max_length=100)


class CvImportReviewBemenet(ApiModel):
    import_id: str = Field(min_length=36, max_length=36)
    approved_text: str = Field(min_length=1, max_length=120_000)


def _akcio_lista(state: CareerState | None) -> dict:
    """Mit enged az állapotgép, és abból mi van ténylegesen bekötve.

    A kettő szándékosan külön: az `allowed_actions` a kanonikus terv
    szerinti lehetőség, az `available_actions` az, amire ma van modul.
    A felület csak az utóbbit kínálja fel, így nem fut 501-be.
    """
    if state is None:
        return {"allowed_actions": [], "available_actions": []}
    engedett = allowed_actions(state)
    return {
        "allowed_actions": [akcio.value for akcio in engedett],
        "available_actions": [
            akcio.value for akcio in engedett if vegrehajthato(akcio)
        ],
    }


def _active_intent_and_readiness(user_id: str, session_id: str | None, profile: dict):
    workflow = workflow_lekeres_vagy_letrehozas(user_id, session_id)
    intent = None
    readiness = None
    if workflow and workflow.get("intent"):
        try:
            intent = CareerIntent(workflow["intent"])
            readiness = profile_readiness(intent, profile)
        except ValueError:
            pass
    return workflow, intent, readiness


@app.get("/api/v1/profile")
def profile_get_vegpont(felhasznalo=Depends(jelenlegi_felhasznalo)):
    """A saját profil vázlata, megerősített adatai és célfüggő hiányai."""
    user_id = str(felhasznalo.id)
    profile = profile_get_or_create(user_id)
    if not profile:
        raise HTTPException(503, "A karrierprofil nem érhető el.")
    session_id = session_lekeres_vagy_letrehozas(user_id)
    workflow, intent, readiness = _active_intent_and_readiness(
        user_id, session_id, profile
    )
    aktualis_allapot = None
    if workflow and workflow.get("current_state"):
        try:
            aktualis_allapot = CareerState(workflow["current_state"])
        except ValueError:
            aktualis_allapot = None
    return {
        **_akcio_lista(aktualis_allapot),
        "id": profile["id"],
        "draft_data": profile.get("draft_data") or {},
        "draft_version": profile.get("draft_version", 0),
        "confirmed_data": profile.get("confirmed_data") or {},
        "active_snapshot_id": profile.get("active_snapshot_id"),
        "active_intent": intent.value if intent else None,
        "current_state": workflow.get("current_state") if workflow else None,
        "readiness": readiness,
        "allowed_fields": sorted(ALLOWED_FIELDS),
    }


@app.patch("/api/v1/profile/draft")
def profile_draft_vegpont(
    bemenet: ProfileDraftPatchBemenet,
    felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """Felhasználói adatot vázlatba ment; ettől még nem lesz igazolt tény."""
    user_id = str(felhasznalo.id)
    try:
        profile = profile_update_draft(user_id, bemenet.fields)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if not profile:
        raise HTTPException(409, "A profil közben megváltozott. Töltsd újra.")
    session_id = session_lekeres_vagy_letrehozas(user_id)
    gps_esemeny_rogzitese(
        user_id,
        session_id,
        "profile_draft_created",
        {"fields": sorted(bemenet.fields), "draft_version": profile["draft_version"]},
        actor="user",
    )
    return {
        "ok": True,
        "draft_data": profile.get("draft_data") or {},
        "draft_version": profile["draft_version"],
        "confirmed": False,
    }


@app.post("/api/v1/profile/confirm")
def profile_confirm_vegpont(
    bemenet: ProfileConfirmBemenet,
    felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """Kifejezett jóváhagyással snapshotot készít és ellenőrzi a profilkaput."""
    user_id = str(felhasznalo.id)
    try:
        snapshot = profile_confirm(user_id, bemenet.fields, bemenet.reason)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if not snapshot:
        raise HTTPException(409, "A profil megerősítése nem sikerült.")

    profile = profile_get_or_create(user_id)
    session_id = session_lekeres_vagy_letrehozas(user_id)
    workflow, intent, readiness = _active_intent_and_readiness(
        user_id, session_id, profile
    )
    state_changed = False
    current_state = None
    if workflow and intent:
        current_state = CareerState(workflow["current_state"])
        action = (
            CareerAction.PROFIL_MEGEROSITESE
            if readiness and readiness["ready"]
            else CareerAction.PROFIL_ADATOK_BEKERESE
        )
        target_state = next_state(current_state, action)
        if target_state is not None:
            context = dict(workflow.get("context") or {})
            context["profile_snapshot_id"] = snapshot["id"]
            if not workflow_frissites(
                user_id, workflow["id"], target_state, intent, context
            ):
                raise HTTPException(503, "A profilállapot mentése nem sikerült.")
            current_state = target_state
            state_changed = True

    event_id = gps_esemeny_rogzitese(
        user_id,
        session_id,
        # A career_gps_events zárt típuslistájának eleme. Korábban itt egy
        # nem engedélyezett típus szerepelt, ezért a beszúrás minden
        # megerősítésnél csendben elbukott, és az audit nyom elveszett.
        "profile_fact_confirmed",
        {
            "snapshot_id": snapshot["id"],
            "version": snapshot["version"],
            "fields": sorted(bemenet.fields),
            "ready_for_intent": bool(readiness and readiness["ready"]),
        },
        actor="user",
    )
    gps_snapshot_frissites(
        user_id,
        "profil",
        "megerositett" if readiness and readiness["ready"] else "ellenorzendo",
        event_id,
    )
    return {
        **_akcio_lista(current_state),
        "ok": True,
        "snapshot_id": snapshot["id"],
        "snapshot_version": snapshot["version"],
        "readiness": readiness,
        "current_state": current_state.value if current_state else None,
        "state_changed": state_changed,
    }


@app.post("/api/v1/profile/import")
async def profile_import_vegpont(
    fajl: UploadFile = File(...),
    felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """PDF-feltöltés és szövegkinyerés; még nem erősít meg profiltényt."""

    content = await read_validated_pdf(fajl)
    try:
        result = cv_import_create(
            str(felhasznalo.id),
            fajl.filename or "cv.pdf",
            content,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if not result:
        raise HTTPException(503, "A CV importálása nem sikerült.")
    return result


@app.get("/api/v1/profile/imports/{import_id}")
def profile_import_get_vegpont(
    import_id: str,
    felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """Egy saját CV-import ellenőrzési állapotát adja vissza."""

    result = cv_import_get(str(felhasznalo.id), import_id)
    if not result:
        raise HTTPException(404, "A CV-import nem található.")
    return result


@app.post("/api/v1/profile/facts/review")
def profile_facts_review_vegpont(
    bemenet: CvImportReviewBemenet,
    felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """Külön felhasználói jóváhagyással aktiválja az átnézett CV-t."""

    user_id = str(felhasznalo.id)
    try:
        approved_import = cv_import_mark_approved(
            user_id,
            bemenet.import_id,
            bemenet.approved_text,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    if not approved_import:
        raise HTTPException(404, "A CV-import nem található.")

    try:
        draft = profile_update_draft(
            user_id,
            {"cv_document_id": bemenet.import_id},
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if not draft:
        raise HTTPException(409, "A profil közben megváltozott. Töltsd újra.")

    confirmation = profile_confirm_vegpont(
        ProfileConfirmBemenet(
            fields=["cv_document_id"],
            reason="cv_extraction_reviewed",
        ),
        felhasznalo,
    )
    return {
        **confirmation,
        "import": approved_import,
    }


@app.get("/api/v1/career-gps")
def career_gps_vegpont(felhasznalo=Depends(jelenlegi_felhasznalo)):
    """
    A bejelentkezett felhasználó aktuális Career GPS állapota, területenként
    (profil, karriercél, piaci kép, felkészültség, pályázás, portfólió,
    speciális út). A private.career_gps_snapshots táblából olvas -- ez az
    events-naplóból már összegzett, gyorsan olvasható nézet.
    """
    return {"teruletek": gps_projekcio(str(felhasznalo.id))}


# ── CÉGINFÓ ───────────────────────────────────────────────────

class CeginfoBemenet(ApiModel):
    ceg_nev: str = Field(max_length=300)


@app.post("/ceginfo")
def ceginfo_vegpont(
    bemenet: CeginfoBemenet,
    _felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """
    Céginfó cache-first: ha 30 napon belül már lekérdeztük ezt a céget,
    az adatbázisból jön (0 Ft) -- csak ismeretlen/lejárt cégnél megy ki
    élőben (SerpAPI + OpenAI, pár filléres költség).
    """
    return ceginfo_kereses(bemenet.ceg_nev)


class SkillGapBemenet(ApiModel):
    cv_szoveg: str = Field(default="", max_length=120_000)
    keszsegek: list = Field(default_factory=list)


@app.post("/skill-gap-elemzes")
def skill_gap_elemzes_vegpont(
    bemenet: SkillGapBemenet,
    _felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """
    Melyik piaci elvárás van meg / hiányzik a CV-ből, jelentés alapján
    (szinonima is számít). VALÓDI Gemini-hívás -- jelenleg ingyenes
    egyetemi kerettel. Üres cv_szoveg/keszsegek esetén NEM hív API-t.
    """
    return skill_gap_elemzes(bemenet.cv_szoveg, bemenet.keszsegek)


class TanacsadoVelemenyBemenet(ApiModel):
    szakma: str = Field(max_length=200)
    stat: dict


@app.post("/tanacsado-velemeny")
def tanacsado_velemeny_vegpont(
    bemenet: TanacsadoVelemenyBemenet,
    _felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """
    Rövid, közérthető karrier-tanács a /szakma-statisztika végpont
    adataiból (+ KSH-átlagbér, ha van). VALÓDI Gemini-hívás -- jelenleg
    ingyenes egyetemi kerettel. Üres stat esetén NEM hív API-t.
    """
    return {"velemeny": tanacsado_velemeny(bemenet.szakma, bemenet.stat)}


# ── AUTH (Supabase Auth -- email + jelszó) ────────────────────

class RegisztracioBemenet(ApiModel):
    email: str = Field(min_length=3, max_length=320)
    jelszo: str = Field(min_length=12, max_length=128)


@app.post("/auth/regisztracio")
def regisztracio_vegpont(
    bemenet: RegisztracioBemenet,
    _=Depends(auth_keres_limit),
):
    """
    Új fiók létrehozása a Supabase Auth-ban. A jelszó-tárolást, -hash-elést
    és az email-küldést (ha a projekt beállítása szerint kell megerősítés)
    teljes egészében a Supabase saját GoTrue-szolgáltatása végzi -- mi nem
    nyúlunk jelszóhoz.
    """
    db = friss_auth_kliens()
    try:
        valasz = db.auth.sign_up({"email": bemenet.email, "password": bemenet.jelszo})
    except Exception:
        raise HTTPException(400, "A regisztráció nem sikerült.")
    return {
        "id": valasz.user.id if valasz.user else None,
        "email": valasz.user.email if valasz.user else None,
        "megerositest_igenyel": valasz.session is None,
    }


class BejelentkezesBemenet(ApiModel):
    email: str = Field(min_length=3, max_length=320)
    jelszo: str = Field(min_length=1, max_length=128)


@app.post("/auth/bejelentkezes")
def bejelentkezes_vegpont(
    bemenet: BejelentkezesBemenet,
    _=Depends(auth_keres_limit),
):
    """
    Belépés email + jelszóval. Sikeres belépéskor egy access_tokent ad
    vissza -- ezt kell a további kéréseknél az "Authorization: Bearer <token>"
    fejlécben elküldeni, hogy a védett végpontok beengedjék a felhasználót.
    """
    db = friss_auth_kliens()
    try:
        valasz = db.auth.sign_in_with_password(
            {"email": bemenet.email, "password": bemenet.jelszo}
        )
    except Exception:
        raise HTTPException(401, "Hibás email cím vagy jelszó.")
    return {
        "access_token": valasz.session.access_token,
        "email": valasz.user.email,
    }


@app.get("/en")
def en_vegpont(felhasznalo=Depends(jelenlegi_felhasznalo)):
    """
    Védett teszt-végpont: CSAK érvényes bejelentkezéssel válaszol. Ez
    bizonyítja, hogy a védelem ténylegesen működik, nem csak papíron --
    érvénytelen/hiányzó tokennel 401-et ad, nem az adatokat.
    """
    return {"id": felhasznalo.id, "email": felhasznalo.email}


# ── STORAGE (CV-fájl tárolása, bejelentkezéshez kötve) ────────

CV_BUCKET = "cv-fajlok"


@app.post("/cv-feltoltes")
async def cv_feltoltes_vegpont(fajl: UploadFile = File(...),
                                felhasznalo=Depends(jelenlegi_felhasznalo)):
    """
    A bejelentkezett felhasználó CV-jét (PDF) elmenti a Supabase Storage-ba,
    a SAJÁT felhasználói ID-jéhez kötött útvonalon (más nem érheti el).
    Ha már van mentett CV-je, felülírja (egy CV / felhasználó, egyszerűség
    kedvéért -- verziózás később, ha kell).
    """
    tartalom = await read_validated_pdf(fajl)

    db = kliens()
    if not db:
        raise HTTPException(503, "Az adatbázis-kapcsolat nem elérhető.")
    utvonal = f"{felhasznalo.id}/cv.pdf"
    try:
        db.storage.from_(CV_BUCKET).upload(
            utvonal, tartalom,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
    except Exception:
        raise HTTPException(500, "Sikertelen feltöltés.")
    return {"ok": True, "utvonal": utvonal, "meret_kb": round(len(tartalom) / 1024, 1)}


@app.get("/cv-letoltes")
def cv_letoltes_vegpont(felhasznalo=Depends(jelenlegi_felhasznalo)):
    """
    Egy rövid élettartamú, aláírt letöltési linket ad a bejelentkezett
    felhasználó SAJÁT CV-jéhez (5 percig érvényes -- nem egy örökre nyitva
    álló link, hogy ne lehessen továbbküldeni/visszaélni vele).
    """
    db = kliens()
    if not db:
        raise HTTPException(503, "Az adatbázis-kapcsolat nem elérhető.")
    utvonal = f"{felhasznalo.id}/cv.pdf"
    try:
        valasz = db.storage.from_(CV_BUCKET).create_signed_url(utvonal, 300)
    except Exception:
        raise HTTPException(404, "Nincs mentett CV-d.")
    return {"url": valasz.get("signedURL") or valasz.get("signedUrl"),
            "lejar_masodperc": 300}
