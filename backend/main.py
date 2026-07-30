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
from uuid import UUID

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
from utils.flow_agy import (
    # A köszöntés tartaléka. A végpontnak is szüksége van rá: ha a modell
    # üres szöveget ad, a válasz nem mehet ki üresen a kliensnek.
    _belepes_tartalek,
    # A köszöntés válaszgombjai. Determinisztikus, ezért kódból jön: a modell
    # csak MEGTUDJA, hogy mi lesz a gombokon, nem ő találja ki.
    belepes_valaszlehetosegek,
    flow_belepes_utan,
    flow_dontes,
    flow_kiertekeles,
    flow_vendeg_valasz,
)
from utils.flow_allapot import (
    session_lekeres_vagy_letrehozas,
    elozmenyek_lekerese,
    uzenet_mentese,
    vendeg_elozmeny_atadasa,
    workflow_lekeres_vagy_letrehozas,
    workflow_frissites,
    workflow_kontextus_frissites,
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
from backend.cv_szakma_javaslat import celmunkakor_javaslatok
from backend.cv_import_service import (
    cv_import_create,
    cv_import_get,
    cv_import_mark_approved,
)
from backend.app_ismeret import alkalmazas_ismeret, elerheto_lepesek
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
    read_validated_cv_file,
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


class FlowVendegElozmeny(ApiModel):
    """Egy korábbi üzenet a vendég-beszélgetésből."""

    szerep: Literal["user", "flow"]
    szoveg: str = Field(min_length=1, max_length=600)


class FlowUzenetBemenet(ApiModel):
    """A /flow-chat utódja: nincs 'elozmenyek' mező, mert a backend saját
    maga tárolja és olvassa vissza a beszélgetést (private.flow_messages) --
    nem a kliens állítása szerint dolgozik."""
    kerdes: str = Field(max_length=8_000)
    # Átmeneti kompatibilitási mező: a backend szándékosan figyelmen kívül
    # hagyja. Személyre szabáshoz csak a szerveroldali, megerősített profil jó.
    profil: dict = Field(default_factory=dict)
    app_ismeret: str = Field(default="", max_length=20_000)
    # Kompatibilitási tartalék: normál esetben a /flow/belepes-utan a sikeres
    # azonosítás után már tartósan átadta a vendégbeszélgetést. Ha az átadás
    # átmenetileg nem sikerült, az első üzenet még megkaphatja kontextusként.
    vendeg_elozmeny: list[FlowVendegElozmeny] = Field(
        default_factory=list, max_length=6
    )


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
        outcome = _muvelet_futtatasa(
            user_id=user_id,
            session_id=session_id,
            workflow=workflow,
            profile=profile,
            akcio=bemenet.action,
            previous_state=previous_state,
            target_state=target_state,
            intent=intent,
            payload=bemenet.payload,
            actor="user",
        )
    except ActionError as exc:
        raise HTTPException(422, str(exc))

    return {
        **_akcio_lista(target_state),
        "ok": True,
        "action": bemenet.action.value,
        "previous_state": previous_state.value,
        "current_state": target_state.value,
        "state_changed": target_state != previous_state,
        "result": outcome.result,
    }


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


class FlowBelepesBemenet(ApiModel):
    """A belépés előtti vendégbeszélgetés, hogy Flow felvehesse a fonalat."""

    vendeg_elozmeny: list[FlowVendegElozmeny] = Field(
        default_factory=list, max_length=6
    )
    # A böngésző egy vendégbeszélgetéshez egyszer készíti. A backend ebből
    # determinisztikus üzenetazonosítókat képez, ezért F5 vagy hálózati
    # újrapróbálás sem tudja megduplázni az átadott előzményt.
    vendeg_atadas_azonosito: UUID | None = None


class FlowCelmunkakorBemenet(ApiModel):
    """A felhasználó által kimondott cél, modellértelmezés nélkül."""

    target_role: str = Field(min_length=1, max_length=200)
    # MELYIK ÚTON MONDTA KI A CÉLT.
    #
    # A célmunkakör rögzítése önmagában is állapotváltás (CEL_TISZTAZATLAN ->
    # CEL_TISZTAZOTT), de az állapotgépnek tudnia kell, MILYEN szándékhoz
    # rögzítjük. A CV-úton ez `cv_frissites`: a felhasználó új CV-változatot
    # kap, nem hibajegyzéket (folyamat_terkep.md 1.).
    #
    # Opcionális, mert a végpont máshonnan is hívható; ilyenkor nem találgatunk
    # szándékot, csak a profiltényt mentjük, ahogy eddig.
    intent: str | None = Field(default=None, max_length=40)


class FlowKezdesBemenet(ApiModel):
    """A kiválasztott, még szándéksemleges kezdőút."""

    utvonal: Literal["cv"]


def _cv_szakma_javaslatok(user_id: str, server_profile: dict) -> list[dict]:
    """A jóváhagyott CV-ből újra előállítható javaslatok.

    A javaslatot nem kell külön böngészőállapotként tárolni: F5 után is a
    jóváhagyott CV a forrás, ezért ugyanaz a determinisztikus eredmény jön.
    """

    import_id = server_profile.get("cv_document_id")
    if not import_id:
        return []
    cv_import = cv_import_get(user_id, str(import_id))
    if not cv_import or cv_import.get("review_status") != "approved":
        return []
    return celmunkakor_javaslatok(cv_import.get("extracted_text") or "")


@app.post("/api/v1/flow/kezdes")
def flow_kezdes_vegpont(
    bemenet: FlowKezdesBemenet,
    felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """Tartósan megnyitja a kiválasztott kezdőfolyamatot."""

    user_id = str(felhasznalo.id)
    session_id = session_lekeres_vagy_letrehozas(user_id)
    workflow = workflow_lekeres_vagy_letrehozas(user_id, session_id)
    if not workflow:
        raise HTTPException(503, "A karrierfolyamat állapota nem érhető el.")

    context = dict(workflow.get("context") or {})
    mar_aktiv = context.get("active_path") == bemenet.utvonal
    context["active_path"] = bemenet.utvonal
    if not workflow_kontextus_frissites(user_id, workflow["id"], context):
        raise HTTPException(503, "A kiválasztott folyamat mentése nem sikerült.")

    flow_uzenet = (
        "Rendben. Töltsd fel a CV-det; előbb megmutatom a kinyert "
        "szöveget, és csak a jóváhagyásod után lépünk tovább."
    )
    if not mar_aktiv:
        uzenet_mentese(user_id, session_id, "user", "Van CV-m")
        uzenet_mentese(user_id, session_id, "flow", flow_uzenet)

    return {
        "ok": True,
        "active_view": "cv_feltoltes",
        "uzenet": flow_uzenet,
        "current_state": workflow.get("current_state"),
    }


@app.post("/api/v1/flow/belepes-utan")
def flow_belepes_utan_vegpont(
    bemenet: FlowBelepesBemenet,
    felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """Belépéskor átveszi vagy visszatölti Flow tartós beszélgetését.

    Új felhasználónál Flow megszólal, visszatéréskor viszont nem gyárt újabb
    köszöntést minden F5-re: a már eltárolt beszélgetést adja vissza. A
    vendégelőzmény csak sikeres, azonosított belépés után kerül a fiókhoz.
    """
    user_id = str(felhasznalo.id)
    session_id = session_lekeres_vagy_letrehozas(user_id)
    profile = profile_get_or_create(user_id) or {}
    server_profile = dict(profile.get("confirmed_data") or {})
    vendeg_sorok = [
        {"szerep": sor.szerep, "szoveg": sor.szoveg}
        for sor in bemenet.vendeg_elozmeny
    ]

    # Még az átadás előtt olvasunk: ebből tudjuk, hogy tényleg új belépésről
    # van-e szó. A tokenfrissítés és az F5 nem új beszélgetés.
    korabbi_uzenetek = elozmenyek_lekerese(user_id, session_id, 50)
    atadas_allapot = vendeg_elozmeny_atadasa(
        user_id,
        session_id,
        bemenet.vendeg_atadas_azonosito,
        vendeg_sorok,
    )
    uj_vendeg_atadas = atadas_allapot == "atadva"

    # AMIT MÁR TÁROLUNK RÓLA, AZT NE KÉRDEZZÜK MEG ÚJRA.
    #
    # A köszöntés eddig csak a nevet és a GPS-területeket kapta meg, ezért egy
    # visszatérő felhasználót is úgy fogadott, mintha most találkoznának:
    # „mi hozott ide?" -- pedig a folyamat állapota, a célmunkaköre és a
    # korábbi beszélgetése is ott van az adatbázisban.
    workflow = workflow_lekeres_vagy_letrehozas(user_id, session_id)
    celmunkakor = str(server_profile.get("target_role") or "")
    cv_javaslatok = _cv_szakma_javaslatok(user_id, server_profile)
    cv_szakma = str((cv_javaslatok[0] if cv_javaslatok else {}).get("szakma") or "")
    van_cv = bool(server_profile.get("cv_document_id"))
    active_path = str((workflow or {}).get("context", {}).get("active_path") or "")
    active_view = (
        "cv_feltoltes"
        if active_path == "cv" and not van_cv
        else "cv_cel"
        if active_path == "cv" and van_cv and not celmunkakor
        else None
    )
    uj_koszontes = not korabbi_uzenetek or uj_vendeg_atadas
    if uj_koszontes:
        uzenet = flow_belepes_utan(
            nev=_megszolitas(felhasznalo, server_profile),
            vendeg_elozmeny=vendeg_sorok,
            gps_osszefoglalo=gps_projekcio(user_id),
            korabbi_allapot=(workflow or {}).get("current_state") or "",
            celmunkakor=celmunkakor,
            cv_szakma=cv_szakma,
            van_cv=van_cv,
            utolso_uzenetek=korabbi_uzenetek,
        )
        # A VÉGPONT NEM ADHAT VISSZA ÜRES ÜZENETET.
        if not (uzenet or "").strip():
            uzenet = _belepes_tartalek(
                _megszolitas(felhasznalo, server_profile),
                celmunkakor,
                cv_szakma,
                van_cv,
            )
        uzenet_mentese(user_id, session_id, "flow", uzenet)

    # A vendégbeszélgetés Flow memóriájának része, nem a belépett felületé.
    # A tárolt forrásjelölés alapján minden betöltésnél kiszűrjük, ezért F5
    # után sem jelenik meg újra a vendégchat.
    uzenetek = elozmenyek_lekerese(user_id, session_id, 50, False)
    if not uzenetek:
        # Adatbázis-kimaradásnál a kliens akkor se maradjon üresen.
        uzenet = _belepes_tartalek(
            _megszolitas(felhasznalo, server_profile),
            celmunkakor,
            cv_szakma,
            van_cv,
        )
        uzenetek = [{"szerep": "flow", "szoveg": uzenet}]
        uj_koszontes = True
    else:
        uzenet = uzenetek[-1]["szoveg"]

    return {
        "uzenet": uzenet,
        "uzenetek": uzenetek,
        "uj_koszontes": uj_koszontes,
        "vendeg_atadas_allapot": atadas_allapot,
        "megszolitas_hianyzik": not _megszolitas(felhasznalo, server_profile),
        "nev_javaslatok": _nev_javaslatok(felhasznalo),
        # FLOW KÉRDEZ, ÉS ITT VANNAK A VÁLASZOK -- NEM KÁRTYARÁCS.
        #
        # A köszöntés eddig csak szöveget adott, ezért a belépő felhasználó a
        # köszöntés után a kártyarács előtt állt: neki kellett kitalálnia,
        # melyik esetben van. A válaszlehetőségek a beszélgetésnél már be
        # voltak kötve, a köszöntésnél soha -- két külön kódút volt, és csak
        # az egyik készült el.
        #
        # A gombok KÓDBÓL jönnek (`belepes_valaszlehetosegek`), nem a
        # modelltől: a döntés determinisztikus, tehát nem is a modell dolga.
        # Így nem tud olyan gombot kitalálni, ami mögött nincs folyamat.
        "valaszlehetosegek": (
            []
            if active_view
            else belepes_valaszlehetosegek(
                celmunkakor,
                cv_szakma,
                van_cv,
            )
        ),
        "active_view": active_view,
        "valasz_tipus": (
            active_view
            if active_view
            else "szolgaltatas"
            if celmunkakor
            else "celmunkakor"
            if van_cv
            else "kezdes"
        ),
    }


def _cel_megerositese(
    user_id: str,
    session_id: str | None,
    kert_intent: str | None,
) -> dict:
    """A célmunkakör rögzítése után egy lépés az állapotgépen.

    Csak a `CEL_TISZTAZATLAN` állapotból lép, és csak akkor, ha a kért szándék
    létező és megerősíthető. Minden más esetben nem történik semmi -- egy
    állapotgép nem attól jó, hogy mindig lép, hanem attól, hogy csak
    engedélyezettet lép.

    A visszaadott szótár a kliensnek szól: ugyanazok a mezők, mint a
    `/api/v1/workflow/intent` válaszában, hogy a felület ne lássa másnak
    ugyanazt az állapotot.
    """

    if not kert_intent:
        return {}
    try:
        intent = CareerIntent(kert_intent)
    except ValueError:
        # Ismeretlen szándék: a profiltény mentése ettől még érvényes marad.
        # NEM hiba, mert a hívó nem is köteles szándékot küldeni.
        return {}

    workflow = workflow_lekeres_vagy_letrehozas(user_id, session_id)
    if not workflow:
        return {}
    try:
        allapot = CareerState(workflow["current_state"])
    except ValueError:
        return {}

    cel_allapot = confirm_intent_transition(allapot, intent)
    if cel_allapot is None:
        # Nem a kiindulóállapotban vagyunk, vagy a szándék nem megerősíthető.
        # A folyamat már túl van ezen a lépésen -- nincs mit tenni.
        return {}

    if not workflow_frissites(
        user_id,
        workflow["id"],
        cel_allapot,
        intent,
        dict(workflow.get("context") or {}),
    ):
        raise HTTPException(503, "A folyamat állapotának mentése nem sikerült.")

    gps_esemeny_rogzitese(
        user_id,
        session_id,
        # A `career_gps_events` ZÁRT típuslistájának eleme. Nem engedélyezett
        # névnél a beszúrás csendben elbukna, és az audit nyom veszne el --
        # ez a hiba egyszer már megtörtént a profilmegerősítésnél.
        "career_intent_confirmed",
        {"intent": intent.value, "from_state": allapot.value},
        actor="user",
    )
    return {
        **_akcio_lista(cel_allapot),
        "current_state": cel_allapot.value,
        "state_changed": True,
    }


@app.post("/api/v1/flow/celmunkakor")
def flow_celmunkakor_vegpont(
    bemenet: FlowCelmunkakorBemenet,
    felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """Menti a kimondott célt, majd Flow felteszi az egyetlen következő kérdést.

    A célmunkakört nem a modell találja ki és nem a kliens tartja életben:
    megerősített profiltény lesz. Emiatt F5, másik lap vagy új munkamenet után
    is ugyanonnan folytatható a folyamat.
    """

    user_id = str(felhasznalo.id)
    target_role = " ".join(bemenet.target_role.split())
    try:
        draft = profile_update_draft(user_id, {"target_role": target_role})
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if not draft:
        raise HTTPException(409, "A célmunkakör mentése közben változott a profil.")

    confirmation = profile_confirm_vegpont(
        ProfileConfirmBemenet(
            fields=["target_role"],
            reason="flow_target_role_confirmation",
        ),
        felhasznalo,
    )
    session_id = session_lekeres_vagy_letrehozas(user_id)

    # A CÉL KIMONDÁSA MAGA A MEGERŐSÍTÉS -- NEM KELL UTÁNA MÉG EGY GOMB.
    #
    # Mérve (2026-07-30): a `career_profiles.confirmed_data` már tartalmazta a
    # `target_role`-t, a `career_workflows` mégis `CEL_TISZTAZATLAN`-ban állt,
    # `intent: null`-lal. Az ok: a `/api/v1/profile/confirm` csak akkor vált
    # állapotot, ha a workflow-nak MÁR van szándéka -- azt viszont kizárólag a
    # `/api/v1/workflow/intent` végpont írja be, ami egy külön gombnyomás.
    #
    # Így a felhasználó kimondta a célját, a rendszer el is mentette, és utána
    # semmi nem történt: a folyamat beragadt a kiindulóállapotban, és a
    # CV-feldolgozás következő szakasza meg sem nyílt.
    #
    # A spec 2.7 kimondja: a felhasználó újabb szolgáltatásválasztása nélkül
    # fut tovább a lánc. Ezért a célmunkakör rögzítésekor itt lépünk egyet --
    # ugyanazon a determinisztikus kapun (`confirm_intent_transition`), amit a
    # gomb is használ. Nem a modell dönt, és nem is a kliens: az állapotgép.
    allapotvaltas = _cel_megerositese(user_id, session_id, bemenet.intent)

    profile = profile_get_or_create(user_id) or {}
    cv_javaslatok = _cv_szakma_javaslatok(
        user_id,
        dict(profile.get("confirmed_data") or {}),
    )
    cv_szakma = str((cv_javaslatok[0] if cv_javaslatok else {}).get("szakma") or "")
    palyavaltas = bool(
        cv_szakma and cv_szakma.casefold() != target_role.casefold()
    )
    if palyavaltas:
        flow_uzenet = (
            f"A CV-d alapján {cv_szakma}, a célod pedig {target_role}. "
            "Ez pályaváltás. A következő elemzésben a közös készségeket és "
            "a hiányokat is külön kell választanunk. Előbb nézzem át ehhez "
            "a CV-det, vagy mutassam meg a cél szakma piacát?"
        )
    else:
        flow_uzenet = (
            f"Rendben, a célod: {target_role}. Átnézzem hozzá a CV-det, "
            "vagy előbb mutassam meg, hogyan áll ez a szakma a piacon?"
        )
    valaszlehetosegek = ["Nézd át a CV-met", "Mutasd a piacot"]
    uzenet_mentese(
        user_id,
        session_id,
        "user",
        f"A célmunkaköröm: {target_role}",
    )
    uzenet_mentese(user_id, session_id, "flow", flow_uzenet)

    return {
        **confirmation,
        **allapotvaltas,
        "target_role": target_role,
        "palyavaltas": palyavaltas,
        "uzenet": flow_uzenet,
        "valaszlehetosegek": valaszlehetosegek,
    }


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
        # Szándékosan NEM a kliens által küldött szöveg: az alkalmazás
        # leírása szerveroldali tény, nem a böngésző állítása.
        alkalmazas_ismeret(),
        elozmenyek,
        current_state=previous_state,
        felhasznalo_neve=_megszolitas(felhasznalo, server_profile),
        gps_osszefoglalo=gps_projekcio(user_id),
        vendeg_elozmeny=[
            {"szerep": sor.szerep, "szoveg": sor.szoveg}
            for sor in bemenet.vendeg_elozmeny
        ],
        most_elindithato=elerheto_lepesek(previous_state),
        # A már lefutott szolgáltatások mért eredménye. A műveletek a
        # workflow-kontextusba teszik le („eredmeny_" előtaggal), innen
        # kerül Flow elé -- így tud beszélni arról, ami kijött, ahelyett
        # hogy csak felajánlaná a lépést.
        lefutott_eredmenyek={
            kulcs.removeprefix("eredmeny_"): ertek
            for kulcs, ertek in (workflow.get("context") or {}).items()
            if kulcs.startswith("eredmeny_")
        },
    )

    uzenet_mentese(
        user_id, session_id, "flow", dontes.response_message, dontes.evidence_refs,
    )

    current_state = previous_state
    accepted_action = None
    gps_esemeny = None

    # A karriercél rögzítése FELHASZNÁLÓI aktus, nem a modell döntése.
    # Korábban Flow javaslatát magát tekintettük megerősítésnek, ezért egy
    # odavetett mondatból ("pályamódosító vagyok") máris kipipált célt
    # kapott a Career GPS -- olyat, amiről a felhasználó nem is tudott.
    # Mostantól csak visszakérdezünk; a rögzítés a /workflow/intent
    # végponton történik, kifejezett rábólintás után.
    megerositendo_intent = None
    if (
        dontes.intent is not CareerIntent.BIZONYTALAN
        and dontes.proposed_action is CareerAction.CEL_MEGEROSITESE
        and confirm_intent_transition(previous_state, dontes.intent) is not None
    ):
        megerositendo_intent = dontes.intent.value
    elif dontes.intent is CareerIntent.BIZONYTALAN:
        accepted_action = CareerAction.TISZTAZO_KERDES

    # Flow nemcsak javasol: ha a művelet az aktuális állapotból engedélyezett
    # ÉS be van kötve, itt le is fut -- ugyanazon a kapun, amit a gombok
    # használnak. Így a felhasználónak elég annyit mondania, hogy „nézd át a
    # CV-met", nem kell gombot keresnie.
    eredmeny = None
    muvelet_hiba = None
    javasolt = dontes.proposed_action
    if (
        javasolt is not None
        and javasolt is not CareerAction.CEL_MEGEROSITESE
        and javasolt is not CareerAction.TISZTAZO_KERDES
        and vegrehajthato(javasolt)
    ):
        kovetkezo = next_state(current_state, javasolt)
        aktiv_intent = dontes.intent
        if workflow.get("intent"):
            try:
                aktiv_intent = CareerIntent(workflow["intent"])
            except ValueError:
                pass
        if kovetkezo is not None:
            profile_futtatashoz = profile_get_or_create(user_id) or profile
            try:
                outcome = _muvelet_futtatasa(
                    user_id=user_id,
                    session_id=session_id,
                    workflow=workflow,
                    profile=profile_futtatashoz,
                    akcio=javasolt,
                    previous_state=current_state,
                    target_state=kovetkezo,
                    intent=aktiv_intent,
                    payload={},
                    actor="flow",
                )
            except ActionError as exc:
                # A modul nem futott le, de Flow már megszólalt: a
                # beszélgetés menjen tovább, az állapot ne változzon.
                muvelet_hiba = str(exc)
            else:
                eredmeny = outcome.result
                accepted_action = javasolt
                current_state = kovetkezo

    proposed_action = dontes.proposed_action
    if proposed_action not in allowed_actions(previous_state):
        proposed_action = None

    # A megszólítás bekérése nem a modell jóindulatán múlik: a szerver tudja,
    # hogy nincs név, tehát ő teszi be a kérendő mezők közé. Korábban ezt a
    # promptra bíztuk, és a modell rendszeresen megfeledkezett róla.
    kerendo_mezok = list(dontes.required_fields)
    if not _megszolitas(felhasznalo, server_profile):
        if "display_name" not in kerendo_mezok:
            kerendo_mezok.append("display_name")

    return {
        "workflow_id": workflow["id"],
        "intent": dontes.intent.value,
        "response_message": dontes.response_message,
        "proposed_action": proposed_action.value if proposed_action else None,
        "accepted_action": accepted_action.value if accepted_action else None,
        "required_fields": kerendo_mezok,
        # Flow saját kérdéséhez tartozó válaszgombok. A felületen nincs
        # állandó kártyarács: ha választani kell, Flow kérdez, és ezek
        # jelennek meg az üzenete alatt.
        "valaszlehetosegek": list(dontes.valaszlehetosegek),
        "specialist_request": dontes.specialist_request,
        "confidence": dontes.confidence,
        "szakma": dontes.szakma,
        "previous_state": previous_state.value,
        "current_state": current_state.value,
        "state_changed": current_state != previous_state,
        "eredmeny": eredmeny,
        "muvelet_hiba": muvelet_hiba,
        "megerositendo_intent": megerositendo_intent,
        **_akcio_lista(current_state),
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


def _megszolitas(felhasznalo, megerositett_profil: dict) -> str:
    """A felhasználó keresztneve, ha ismert.

    Sorrend: a saját maga által megerősített profilnév, a saját
    regisztrációs űrlapunkon megadott keresztnév, végül a szolgáltatótól
    kapott teljes név. E-mail címet nem használunk megszólításnak.
    """
    # CSAK AMIT Ő MAGA ERŐSÍTETT MEG.
    #
    # A Google `given_name` mezője magyarul megbízhatatlan: a regisztrációs
    # űrlapon sokan a VEZETÉKNEVET írják a „keresztnév" rovatba. Mérve
    # 2026-07-29: Varga Andrea fiókjában a `given_name` = „Varga", és Flow
    # így „Szia Varga!"-val köszönt.
    #
    # Ezért a Google nevét nem tényként vesszük, hanem JAVASLATKÉNT: a
    # `_nev_javaslatok` felkínálja a teljes név szavait, és a felhasználó egy
    # kattintással eldönti, hogyan szólítsuk. Egy kérdés egyszer, szemben
    # azzal, hogy végig rossz néven szólítjuk.
    sajat = str(megerositett_profil.get("display_name") or "").strip()
    if sajat:
        return sajat

    # AMIT A SAJÁT ŰRLAPUNKON ÍRT BE, AZ IS TŐLE VAN.
    #
    # Az e-mailes regisztráció KÖTELEZŐ „Keresztneved" mezőjének értéke ide
    # kerül. Ez nem a szolgáltató tippje, hanem a felhasználó saját szava --
    # ugyanabba a kategóriába tartozik, mint a fenti megerősített profilnév.
    #
    # Ez eddig kimaradt, és emiatt az e-mailes ág néma hibában állt: a nevet
    # kötelező mezőben megadta, a `user_metadata`-ba be is került, de EGYETLEN
    # sor sem olvasta -- Flow végig úgy viselkedett, mintha nem tudná a nevét,
    # és újra meg újra megkérdezte.
    #
    # A Google `given_name` mezőjét szándékosan NEM olvassuk itt: az a
    # szolgáltatótól jön. Ezért van külön kulcsa annak, amit ő maga írt be.
    metaadat = getattr(felhasznalo, "user_metadata", None) or {}
    sajat_keresztnev = str(metaadat.get("sajat_keresztnev") or "").strip()
    if sajat_keresztnev:
        return sajat_keresztnev

    # RÉGEBBI GOOGLE-FIÓKOK TARTALÉKA.
    #
    # A Google `given_name` mezőjét továbbra sem használjuk, mert magyar
    # névsorrendnél gyakran a vezetéknevet tartalmazza. A teljes név viszont
    # nem találgatás: a felhasználó fiókjának tényleges neve. Inkább ezen
    # szólítjuk, mint hogy a regisztrációnál már megadott nevét újra kérjük.
    return str(metaadat.get("full_name") or metaadat.get("name") or "").strip()


def _nev_javaslatok(felhasznalo) -> list[str]:
    """A teljes névből felkínálható szavak, hogy ne kelljen gépelni.

    Nem döntjük el, melyik a keresztnév -- a Google `full_name` magyarul
    mindkét sorrendben előfordul. Felkínáljuk mindkettőt, és a felhasználó
    egy kattintással választ. Így a javaslat látható, nem rejtett tipp.
    """
    metaadat = getattr(felhasznalo, "user_metadata", None) or {}
    teljes = str(metaadat.get("full_name") or metaadat.get("name") or "").strip()
    szavak = [szo for szo in teljes.split() if len(szo) > 1]
    return szavak[:3]


def _muvelet_futtatasa(
    *,
    user_id: str,
    session_id: str | None,
    workflow: dict,
    profile: dict,
    akcio: CareerAction,
    previous_state: CareerState,
    target_state: CareerState,
    intent: CareerIntent,
    payload: dict,
    actor: str,
):
    """Egyetlen közös végrehajtási út a gomboknak és Flow javaslatainak.

    Azért közös, mert két külön út óhatatlanul elcsúszna egymástól, és a
    szigorúbbik kapu megkerülhetővé válna. A sorrend itt is kötött: a
    modul előbb lefut, és csak sikeres futás után változik az állapot.
    """
    outcome = execute_action(
        akcio,
        ActionContext(
            user_id=user_id,
            workflow=workflow,
            profile=profile,
            payload=payload,
        ),
    )

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
                "action": akcio.value,
                "previous_state": previous_state.value,
                "current_state": target_state.value,
                **outcome.gps_payload,
            },
            actor=actor,
        )
    # A területjelzés eseménynapló nélkül is érvényes: van olyan lépés, ami
    # a folyamat állását változtatja, de nem keletkezik hozzá önálló,
    # auditálandó domain-esemény (utolso_esemeny_id nullable).
    if outcome.gps_terulet:
        gps_snapshot_frissites(
            user_id, outcome.gps_terulet, outcome.gps_allapot, event_id
        )
    return outcome


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
    """CV-feltöltés és szövegkinyerés; még nem erősít meg profiltényt.

    Elfogadott formátumok: PDF, DOCX, JPG és PNG (folyamat_terkep.md 2.3).
    A `formatum` nem a kliens állítása, hanem magic byte-tal ellenőrzött tény --
    a szövegkinyerés ez alapján választ utat.
    """

    content, formatum = await read_validated_cv_file(fajl)
    try:
        result = cv_import_create(
            str(felhasznalo.id),
            fajl.filename or "cv.pdf",
            content,
            formatum,
            fajl.content_type or "",
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
    korabbi_import = cv_import_get(user_id, bemenet.import_id)
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
    # CÉLMUNKAKÖR-JAVASLAT A JÓVÁHAGYOTT CV-BŐL.
    #
    # A profil eddig csak a `cv_document_id`-t kapta meg -- vagyis
    # „ellenőrzött" lett úgy, hogy egyetlen valódi karrieradat sem került
    # bele. Emiatt a célmunkakört külön be kellett gépelni, és addig egyetlen
    # szolgáltatás sem futott le.
    #
    # A javaslatot NEM mentjük automatikusan: egy emberben több szakmai
    # profil is lehet (pénztáros és bolti eladó egyszerre), és a célmunkakör
    # nem azonos a jelenlegivel. A felhasználó választ, mi csak felkínáljuk.
    javaslatok = celmunkakor_javaslatok(bemenet.approved_text or "")
    if javaslatok:
        felismert_szakma = str(javaslatok[0]["szakma"])
        flow_uzenet = (
            f"A CV-d alapján {felismert_szakma}. "
            "Ez lesz a célod, vagy másra készülsz?"
        )
        flow_valaszlehetosegek = [felismert_szakma, "Másra készülök"]
    else:
        flow_uzenet = (
            "A CV-d rendben megérkezett. Milyen pozíció vagy szakma a célod?"
        )
        flow_valaszlehetosegek = []

    # Az átmenet maga is része a tartós beszélgetésnek. Így F5 után nem a
    # CV-feltöltés előtti kérdés jelenik meg újra.
    if not korabbi_import or korabbi_import.get("review_status") != "approved":
        session_id = session_lekeres_vagy_letrehozas(user_id)
        uzenet_mentese(user_id, session_id, "flow", flow_uzenet)

    return {
        **confirmation,
        "import": approved_import,
        "celmunkakor_javaslatok": javaslatok,
        "flow_uzenet": flow_uzenet,
        "flow_valaszlehetosegek": flow_valaszlehetosegek,
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
