# -*- coding: utf-8 -*-
"""FLOW AGYA — tudásbázis-keresés + kiértékelés/válasz generálás.

Keresés: Gemini embedding (ha van kvóta) → pgvector; tartalék: kulcsszavas.
Szöveg: Gemini 2.5 flash (0 Ft). A MODELL CSERÉLHETŐ (később akár GPT).
Szabály: Flow KIZÁRÓLAG a tudásbázisból + a profilból állít, forrással.
"""

import json
import os
import re

import requests

from utils.adatbazis import kliens
from backend.flow_contract import FlowDecision, biztonsagos_alapertelmezes

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
EMBED_URL = "https://api.openai.com/v1/embeddings"  # ~0,000002 USD/kérdés
SZOVEG_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
              "gemini-2.5-flash:generateContent")


# ── KERESÉS ──────────────────────────────────────────────────

def _embedding(szoveg: str):
    r = requests.post(
        EMBED_URL,
        headers={"Authorization": f"Bearer {OPENAI_KEY}"},
        json={"model": "text-embedding-3-small",
              "input": szoveg[:9000], "dimensions": 768}, timeout=30)
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]


def _kulcsszo_kereses(kerdes: str, darab: int) -> list:
    """Tartalék: a kérdés hosszabb szavaira ilike-keresés, találatszám szerint."""
    db = kliens()
    if not db:
        return []
    szavak = [w for w in re.findall(r"\w+", kerdes.lower()) if len(w) >= 5][:6]
    if not szavak:
        return []
    pontok = {}
    for szo in szavak:
        r = (db.table("tudasanyag").select("id, forras, szoveg")
               .ilike("szoveg", f"%{szo}%").limit(20).execute())
        for s in (r.data or []):
            pontok.setdefault(s["id"], {"sor": s, "pont": 0})
            pontok[s["id"]]["pont"] += 1
    rendezett = sorted(pontok.values(), key=lambda x: -x["pont"])
    return [x["sor"] for x in rendezett[:darab]]


def tudas_kereses(kerdes: str, darab: int = 5) -> list:
    """A kérdéshez legjobban illő tudásbázis-szakaszok.
    Embedding-kereséssel, kvóta-hiba esetén kulcsszavas tartalékkal."""
    db = kliens()
    if not db:
        return []
    try:
        vektor = _embedding(kerdes)
        r = db.rpc("tudas_kereses", {"kerdes_embedding": vektor,
                                     "darab": darab}).execute()
        if r.data:
            return r.data
    except Exception as e:
        print(f"[flow] Embedding-kereses nem ment ({e}) — kulcsszavas tartalek.")
    return _kulcsszo_kereses(kerdes, darab)


# ── KÉP-BEOLVASÁS: kézzel írt / szkennelt CV átírása szöveggé ─

def kep_atiras(kep_bytes: bytes, mime: str) -> str:
    """Kézzel írt vagy fotózott önéletrajz átírása géppel írt szöveggé
    (Gemini flash, ingyenes). Üres string, ha nem sikerül."""
    if not GEMINI_KEY or not kep_bytes:
        return ""
    import base64
    try:
        r = requests.post(
            SZOVEG_URL, params={"key": GEMINI_KEY},
            json={"contents": [{"parts": [
                {"inline_data": {"mime_type": mime,
                                 "data": base64.b64encode(kep_bytes).decode()}},
                {"text": "Ez egy önéletrajz fotója vagy szkennelt képe, "
                         "valószínűleg kézzel írva. Írd át PONTOSAN géppel írt "
                         "szöveggé, az eredeti tartalmat megőrizve — semmit ne "
                         "egészíts ki és ne találj ki. Amit nem tudsz elolvasni, "
                         "jelöld így: [olvashatatlan]. Csak az átiratot add "
                         "vissza, magyarázat nélkül."}]}]},
            timeout=120)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"[flow] Kep-atiras hiba: {e}")
        return ""


# ── HANG-BEOLVASÁS: kimondott kérdés átírása szöveggé ────────

def hang_atiras(hang_bytes: bytes, mime: str = "audio/wav") -> str:
    """Hangfelvétel átírása magyar szöveggé (Gemini flash, ingyenes)."""
    if not GEMINI_KEY or not hang_bytes:
        return ""
    import base64
    try:
        r = requests.post(
            SZOVEG_URL, params={"key": GEMINI_KEY},
            json={"contents": [{"parts": [
                {"inline_data": {"mime_type": mime,
                                 "data": base64.b64encode(hang_bytes).decode()}},
                {"text": "Írd át PONTOSAN szöveggé, amit a felvételen mondanak "
                         "(magyarul). Csak az átiratot add vissza, magyarázat "
                         "és kommentár nélkül."}]}]},
            timeout=90)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"[flow] Hang-atiras hiba: {e}")
        return ""


# ── SZÖVEG-GENERÁLÁS ─────────────────────────────────────────

def _gemini_szoveg(prompt: str) -> str:
    r = requests.post(
        SZOVEG_URL, params={"key": GEMINI_KEY},
        json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=90)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


FLOW_SZABALYOK = """SZIGORÚ SZABÁLYOK:
- KIZÁRÓLAG a fenti tudásanyag-szakaszokból és a profilból dolgozz — semmit ne találj ki.
- Erősség-alapú, tegező, meleg de szakmai hang. NEM címkézel, NEM diagnosztizálsz.
- TILOS mentegetőzni vagy leírni, mire nincs adat.
- Ha a jóllét-jelzésben kimerülés vagy megterhelő közeg szerepel: együttérzően
  reagálj, hangsúlyozd, hogy nem az ő hibája, és a tanácsot ehhez igazítsd
  (fenntartható lépések, ne extra terhelés). Említsd meg, hogy szükség esetén
  szakember (munkahelyi mentálhigiénés tanácsadó, pszichológus) is segíthet.
- A végén sorold fel a felhasznált forrásokat: "Források: ..." formában."""

FLOW_SZEMELYISEG = """FLOW SZEMÉLYISÉGE:
Te vagy a legkedvesebb, legempatikusabb, legsegítőkészebb lény, akivel a
felhasználó valaha beszélt. Meleg, emberi, sosem robotikus vagy semleges.
Ha valaki bizonytalan, elveszettnek érzi magát, vagy kiégett, EZT ELŐSZÖR
elismered, mielőtt bármilyen tanácsot adnál. Sosem ítélkezel, sosem
siettetsz. Amikor lehetőséged van rá, konkrét, gyakorlati segítséget adsz,
nem általánosságokat."""

FLOW_IRANYITAS = """ÁLLÁSKERESÉSI SZÁNDÉK FELISMERÉSE ÉS IRÁNYÍTÁS:
Ha a felhasználó jelzi, hogy állást keres / pályázni szeretne / munkát
akar találni:
1. Ha MÉG NEM tudod, milyen szakmában/pozícióban keres állást (sem a
   profilból, sem a beszélgetésből nem derül ki), KÉRDEZD MEG ezt
   természetesen, melegen — ne tegyél be semmilyen jelölést, amíg nincs
   válasz erre.
2. Amint tudod a célszakmát, a válaszod LEGVÉGÉRE (semmi ne kövesse utána)
   illeszd be pontosan ezt a jelölést:
   [FLOW_AKCIO:karrier_ugynok:PONTOS_SZAKMA_NEVE]
   Példa: "...jó, nézzük is meg, mit találunk! [FLOW_AKCIO:karrier_ugynok:szoftvertesztelő]"
   Ha "nincs pontos elképzelése" a szakmáról, ezt is jelezd emberi hangon,
   de próbáld a beszélgetésből kitalálható LEGVALÓSZÍNŰBB célszakmát
   használni a jelölésben — a rendszer úgyis rá tud kérdezni pontosításra.
3. Ha a felhasználó NEM állást keres (csak kérdez valamit, tanácsot kér),
   NE tedd be a jelölést, csak válaszolj a szokásos módon."""


def flow_kiertekeles(profil: dict) -> str:
    """Részletes, személyre szabott kiértékelés a teszt + profil alapján."""
    if not GEMINI_KEY or not profil:
        return ""
    kereso_szoveg = (f"karrier érdeklődés személyiségtípus {profil.get('holland_tipus', '')} "
                     f"karrierhorgony {profil.get('karrierhorgony', '')} "
                     f"munkahelyi jóllét kiégés motiváció")
    szakaszok = tudas_kereses(kereso_szoveg, darab=10)
    tudas = "\n\n".join(
        f"[{s['forras']}]\n{s['szoveg'][:1200]}" for s in szakaszok) or "nincs találat"

    profil_sorok = "\n".join(f"- {k}: {v}" for k, v in profil.items()
                             if k != "erdeklodes" and v)

    prompt = f"""Flow vagy, munka- és szervezetpszichológiai kísérő egy magyar
álláskereső oldalon. Az alábbi PROFIL és TUDÁSANYAG alapján írj személyre
szabott kiértékelést a felhasználónak.

PROFIL:
{profil_sorok}

TUDÁSANYAG-SZAKASZOK:
{tudas}

FELÉPÍTÉS (4 rövid bekezdés, felsorolás nélkül, max 14 mondat):
1. Mit jelent az érdeklődés-típusa — miben erős, milyen munkakörnyezetben
   virágzik (a tudásanyag alapján).
2. Mit jelent a karrierhorgonya — mire figyeljen álláskeresésnél, mi az,
   amit ne adjon fel.
3. Reflektálj a jóllét-jelzésére az előírt hangnemben.
4. Egy bátorító, előremutató zárás: mi a következő jó lépés az oldalon
   (pl. a Karrier Tanácsadó piaci adatai, átjárási térkép — csak ha releváns).
   KIVÉTEL — ha a jóllét-jelzés kimerülést vagy megterhelő munkahelyi közeget
   mutat ÉS ismert a szakmája: itt KONKRÉTAN ajánld fel a váltás
   megvizsgálását — ezen az oldalon (Karrier Tanácsadó fül) a szakmája
   kiválasztása után a „🔀 átjárási lehetőségek” gombbal megnézheti, mely
   rokon szakmákba vihető át a meglévő tudása. Hangsúlyozd: ez csak
   lehetőség, nem elvárás — ő dönt.

{FLOW_SZABALYOK}"""
    try:
        return _gemini_szoveg(prompt)
    except Exception as e:
        print(f"[flow] Kiertekeles hiba: {e}")
        return ""


def flow_valasz(kerdes: str, profil: dict, app_ismeret: str = "",
                elozmenyek: list = None) -> str:
    """Chat-válasz: profil + tudásbázis + app-ismeret alapján."""
    if not GEMINI_KEY or not kerdes:
        return ""
    szakaszok = tudas_kereses(kerdes, darab=10)
    tudas = "\n\n".join(
        f"[{s['forras']}]\n{s['szoveg'][:1000]}" for s in szakaszok) or "nincs találat"
    profil_sorok = "\n".join(f"- {k}: {v}" for k, v in (profil or {}).items() if v)
    elozmeny_sorok = "\n".join(
        f"{'Felhasználó' if e['szerep'] == 'user' else 'Flow'}: {e['szoveg']}"
        for e in (elozmenyek or [])[-6:])

    prompt = f"""Flow vagy, munka- és szervezetpszichológiai kísérő egy magyar
álláskereső oldalon (Karrier-Ügynökség).

AZ OLDAL MŰKÖDÉSE (ha az oldalról kérdez, ebből igazítsd el):
{app_ismeret[:4000]}

A FELHASZNÁLÓ PROFILJA (ha üres, még nem ismered):
{profil_sorok or "még nincs adat"}

TUDÁSANYAG-SZAKASZOK a kérdéshez:
{tudas}

EDDIGI BESZÉLGETÉS:
{elozmeny_sorok or "ez az első üzenet"}

A FELHASZNÁLÓ KÉRDÉSE: {kerdes}

Válaszolj röviden (max 8 mondat), tegezve, melegen és szakmailag.
{FLOW_SZEMELYISEG}
{FLOW_SZABALYOK}
- Ha a kérdéshez nincs releváns tudásanyag ÉS nem az oldalról szól, mondd ki
  őszintén, hogy erre nincs megbízható anyagod, és ajánld, mit tudsz helyette.
- Ha krízist, önsértést, akut lelki válságot jelez: együttérzően reagálj, és
  javasold, hogy beszéljen szakemberrel vagy hívja a 116-123 lelkisegély-számot.

{FLOW_IRANYITAS}"""
    try:
        return _gemini_szoveg(prompt)
    except Exception as e:
        print(f"[flow] Valasz hiba: {e}")
        return ""


# ── STRUKTURÁLT DÖNTÉS (FlowDecision) ─────────────────────────
# Ez váltja fel a fenti szabad szöveges [FLOW_AKCIO: ...] jelölést a
# 02-flow-career-gps.md terv szerint: Flow mostantól KIZÁRÓLAG ezt a JSON
# szerkezetet adhatja vissza, nincs kliensoldali regex-parszolás.

FLOW_DECISION_SEMA = {
    "type": "OBJECT",
    "properties": {
        "intent": {
            "type": "STRING",
            "enum": [
                "allast_keres_van_cv",
                "allast_keres_nincs_cv",
                "palyavaltas",
                "altalanos_kerdes",
                "bizonytalan",
            ],
        },
        "response_message": {"type": "STRING"},
        "proposed_action": {
            "type": "STRING",
            "enum": ["karrier_ugynok_inditasa", "nincs"],
        },
        "required_fields": {"type": "ARRAY", "items": {"type": "STRING"}},
        "specialist_request": {
            "type": "STRING",
            "enum": [
                "career_advisor",
                "application_materials_agent",
                "portfolio_designer",
                "nincs",
            ],
        },
        "evidence_refs": {"type": "ARRAY", "items": {"type": "STRING"}},
        "confidence": {"type": "NUMBER"},
        "szakma": {"type": "STRING"},
    },
    "required": ["intent", "response_message"],
}


def _gemini_json(prompt: str) -> dict:
    r = requests.post(
        SZOVEG_URL, params={"key": GEMINI_KEY},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": FLOW_DECISION_SEMA,
            },
        }, timeout=90)
    r.raise_for_status()
    szoveg = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(szoveg)


def flow_dontes(kerdes: str, profil: dict, app_ismeret: str = "",
                 elozmenyek: list = None) -> FlowDecision:
    """Flow strukturált döntése egy üzenetre. Ez a hivatalos, tervben
    rögzített szerződés (lásd backend/flow_contract.py) — nem szabad szöveg,
    nem regex. Két kísérletet tesz érvényes JSON-ra, utána biztonságos
    fallbackra vált (a felhasználó munkája/üzenete így sem vész el)."""
    if not GEMINI_KEY or not kerdes:
        return biztonsagos_alapertelmezes(
            "Most nem érem el a háttérrendszert. Írd le még egyszer, miben "
            "segíthetek — az üzeneted nem veszett el."
        )

    szakaszok = tudas_kereses(kerdes, darab=8)
    tudas = "\n\n".join(
        f"[{s['forras']}]\n{s['szoveg'][:1000]}" for s in szakaszok) or "nincs találat"
    profil_sorok = "\n".join(f"- {k}: {v}" for k, v in (profil or {}).items() if v)
    elozmeny_sorok = "\n".join(
        f"{'Felhasználó' if e['szerep'] == 'user' else 'Flow'}: {e['szoveg']}"
        for e in (elozmenyek or [])[-8:])

    alap_prompt = f"""Flow vagy, a Karrier-Ügynökség csapatának menedzsere —
NEM egy általános chatbot. Feladatod: felismerni a felhasználó szándékát,
és a séma szerinti strukturált döntést visszaadni. Te magad nem írsz
adatbázist, nem indítasz automatikusan semmit — csak javasolsz.

{FLOW_SZEMELYISEG}

AZ OLDAL MŰKÖDÉSE:
{app_ismeret[:4000]}

A FELHASZNÁLÓ PROFILJA (ha üres, még nem ismered):
{profil_sorok or "még nincs adat"}

TUDÁSANYAG-SZAKASZOK a kérdéshez:
{tudas}

EDDIGI BESZÉLGETÉS:
{elozmeny_sorok or "ez az első üzenet"}

A FELHASZNÁLÓ ÚJ ÜZENETE: {kerdes}

DÖNTÉSI SZABÁLYOK:
- intent="allast_keres_van_cv": ha jelzi, hogy van CV-je és állást keres.
- intent="allast_keres_nincs_cv": ha állást keresne, de nincs CV-je vagy
  nem világos, hogy van-e.
- intent="palyavaltas": ha pályát vagy országot váltana, bizonytalan az irány.
- intent="altalanos_kerdes": ha csak kérdez valamit, nem indít folyamatot.
- intent="bizonytalan": ha nem egyértelmű a szándék — ilyenkor NE tegyél be
  proposed_action-t, hanem a response_message-ben tégy fel egy rövid,
  pontosító kérdést.
- proposed_action="karrier_ugynok_inditasa" CSAK akkor, ha allast_keres_*
  szándék ÉS ismert a célszakma (szakma mező kitöltve). Ha a szakma még
  nem ismert, hagyd "nincs"-en, és a required_fields tartalmazza: "szakma".
- response_message: ez jelenik meg a felhasználónak — rövid (max 6 mondat),
  meleg, tegező, konkrét. Sosem tartalmaz jelölést vagy technikai szöveget.
- confidence: őszinte becslés 0 és 1 között.

{FLOW_SZABALYOK}

Kizárólag a séma szerinti JSON objektumot add vissza, semmi mást — se
magyarázatot, se markdown-jelölést a JSON köré."""

    for kiserlet in range(2):
        prompt = alap_prompt
        if kiserlet == 1:
            prompt += ("\n\nAz előző válaszod nem volt érvényes JSON a séma "
                       "szerint. Javítsd, és KIZÁRÓLAG a JSON objektumot add vissza.")
        try:
            nyers = _gemini_json(prompt)
            if nyers.get("proposed_action") == "nincs":
                nyers["proposed_action"] = None
            if nyers.get("specialist_request") == "nincs":
                nyers["specialist_request"] = None
            return FlowDecision(**nyers)
        except Exception as e:
            print(f"[flow] dontes-parszolas hiba ({kiserlet + 1}. kiserlet): {e}")

    return biztonsagos_alapertelmezes(
        "Nem sikerült pontosan értelmeznem a kérdésed. Mondanád el kicsit "
        "másképp, miben segíthetek?"
    )
