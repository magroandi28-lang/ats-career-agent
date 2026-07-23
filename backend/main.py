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

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
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
from utils.flow_agy import flow_kiertekeles, flow_valasz
from backend.auth import (
    auth_keres_limit,
    friss_auth_kliens,
    jelenlegi_felhasznalo,
)
from backend.security import RequestSecurityMiddleware, read_validated_pdf
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


class FlowChatBemenet(ApiModel):
    kerdes: str = Field(max_length=8_000)
    profil: dict = Field(default_factory=dict)
    app_ismeret: str = Field(default="", max_length=20_000)
    elozmenyek: list = Field(default_factory=list)


@app.post("/flow-chat")
def flow_chat_vegpont(
    bemenet: FlowChatBemenet,
    _felhasznalo=Depends(jelenlegi_felhasznalo),
):
    """
    Flow chat-válasza: profil + tudásbázis (pgvector RAG) + app-ismeret
    alapján. VALÓDI Gemini-hívás. Üres kérdéssel NEM hív API-t.
    """
    return {"valasz": flow_valasz(
        bemenet.kerdes, bemenet.profil, bemenet.app_ismeret, bemenet.elozmenyek
    )}


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
