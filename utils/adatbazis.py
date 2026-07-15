# -*- coding: utf-8 -*-
"""Supabase adatbázis-réteg — utils/adatbazis.py (2. fázis)

Passzív adatgyűjtés: a felhasználói keresések "melléktermékeként"
minden megtalált hirdetést, céget és készséget elmentünk a Supabase-be.
Plusz: céginfó-cache — amit egyszer már lekérdeztünk a SerpAPI-tól,
azt 30 napig az adatbázisból adjuk vissza (kredit-kímélés).

FONTOS ELV: az adatbázis NEM létfeltétel. Ha a .env-ben nincs
SUPABASE_URL / SUPABASE_SERVICE_KEY, vagy a mentés bármiért elhasal,
az alkalmazás ugyanúgy működik tovább — csak épp nem gyűjt.
"""

import datetime
import os

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
# A titkos kulcsot két néven is elfogadjuk: a Supabase új felülete
# "secret key"-nek hívja, a régi "service_role"-nak — ugyanaz a szerepe.
SUPABASE_SERVICE_KEY = (
    os.getenv("SUPABASE_SERVICE_KEY", "")
    or os.getenv("SUPABASE_SECRET_KEY", "")
)

_kliens = None

ERVENYES_KESZSEG_TIPUSOK = ("elvaras", "feladat", "eszkoz", "soft")
ERVENYES_FORRAS_TIPUSOK = ("portal", "ceges", "jooble")


def kliens():
    """Lusta kapcsolódás — csak az első használatkor csatlakozik,
    utána ugyanazt a klienst adja vissza."""
    global _kliens
    if _kliens is not None:
        return _kliens
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("[adatbazis] FIGYELEM: SUPABASE_URL vagy SUPABASE_SERVICE_KEY "
              "hianyzik a .env-bol — a mentes kimarad!")
        return None
    try:
        from supabase import create_client
        _kliens = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return _kliens
    except Exception as e:
        print(f"[adatbazis] Kapcsolodas sikertelen: {e}")
        return None


# ── SZAKMA ───────────────────────────────────────────────────

def szakma_ment(szakma_info: dict):
    """Név alapján upsert; visszaadja a szakma id-jét (vagy None-t)."""
    db = kliens()
    nev = (szakma_info.get("szakma") or "").strip()
    if not db or not nev:
        return None
    r = db.table("szakmak").upsert(
        {"nev": nev, "kategoria": szakma_info.get("szakma_kategoria", "")},
        on_conflict="nev",
    ).execute()
    return r.data[0]["id"] if r.data else None


# ── CÉG + CÉGINFÓ-CACHE ──────────────────────────────────────

def ceg_ment(nev: str):
    db = kliens()
    nev = (nev or "").strip()
    if not db or not nev:
        return None
    r = db.table("cegek").upsert({"nev": nev}, on_conflict="nev").execute()
    return r.data[0]["id"] if r.data else None


def ceginfo_cache_lekerdez(ceg_nev: str, max_nap: int = 30):
    """Ha a cégről van max_nap-nál frissebb céginfónk, azt adjuk vissza —
    így nem kell újra SerpAPI-t hívni. Ha nincs (vagy régi), None."""
    db = kliens()
    if not db or not ceg_nev:
        return None
    try:
        r = db.table("cegek").select("*").eq("nev", ceg_nev.strip()).limit(1).execute()
        if not r.data:
            return None
        sor = r.data[0]
        frissitve = sor.get("ceginfo_frissitve")
        if not frissitve or not sor.get("leiras"):
            return None
        datum = datetime.datetime.fromisoformat(frissitve.replace("Z", "+00:00"))
        kor = datetime.datetime.now(datetime.timezone.utc) - datum
        if kor.days > max_nap:
            return None
        print(f"[adatbazis] Ceginfo a cache-bol: {ceg_nev}")
        return {
            "leiras": sor.get("leiras", ""),
            "meret": sor.get("meret", ""),
            "bersav": sor.get("bersav", ""),
            "fluktuacio": sor.get("fluktuacio", ""),
            "velemenyek": sor.get("velemenyek", ""),
            "figyelmeztetes": sor.get("figyelmeztetes"),
        }
    except Exception as e:
        print(f"[adatbazis] Cache-lekerdezes hiba: {e}")
        return None


def ceginfo_cache_ment(ceg_nev: str, info: dict):
    """A frissen lekérdezett céginfót beírja a cache-be."""
    db = kliens()
    if not db or not ceg_nev or not info:
        return
    try:
        db.table("cegek").upsert({
            "nev": ceg_nev.strip(),
            "leiras": info.get("leiras", ""),
            "meret": info.get("meret", ""),
            "bersav": info.get("bersav", ""),
            "fluktuacio": info.get("fluktuacio", ""),
            "velemenyek": info.get("velemenyek", ""),
            "figyelmeztetes": info.get("figyelmeztetes"),
            "ceginfo_frissitve": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }, on_conflict="nev").execute()
    except Exception as e:
        print(f"[adatbazis] Ceginfo mentes hiba: {e}")


def letezo_linkek(linkek: list) -> set:
    """Megadja, mely linkek vannak MÁR az adatbázisban.
    A gyűjtő script ezzel szűri ki a duplikátumokat MÉG a (pénzbe kerülő)
    készség-kinyerés előtt."""
    db = kliens()
    linkek = [l for l in (linkek or []) if l]
    if not db or not linkek:
        return set()
    try:
        r = db.table("hirdetesek").select("link").in_("link", linkek).execute()
        return {s["link"] for s in (r.data or [])}
    except Exception as e:
        print(f"[adatbazis] Link-ellenorzes hiba: {e}")
        return set()


# ── HIRDETÉSEK + KÉSZSÉGEK MENTÉSE ───────────────────────────

def gyujtes_mentese(szakma_info: dict, allasok: list, keszsegek_per_allas: list = None) -> int:
    """A keresés összes eredményét elmenti (passzív gyűjtés).

    keszsegek_per_allas: az allasok listával párhuzamos lista, elemei
    [{"nev": "...", "tipus": "elvaras"}, ...] alakúak.

    Hibatűrő: bármely lépés elhasalhat, a többi attól még lefut.
    Visszaadja az ÚJ (nem duplikátum) hirdetések számát."""
    db = kliens()
    if not db or not allasok:
        return 0
    if not keszsegek_per_allas:
        keszsegek_per_allas = [[] for _ in allasok]

    szakma_id = None
    try:
        szakma_id = szakma_ment(szakma_info)
    except Exception as e:
        print(f"[adatbazis] Szakma mentes hiba: {e}")

    mentve = 0
    for allas, keszsegek in zip(allasok, keszsegek_per_allas):
        try:
            hirdetes_id = _hirdetes_ment(db, allas, szakma_id)
            if hirdetes_id is None:
                continue  # duplikátum vagy hiányos adat
            mentve += 1
            if keszsegek:
                _keszsegek_ment(db, hirdetes_id, keszsegek)
        except Exception as e:
            print(f"[adatbazis] Hirdetes mentes hiba: {e}")

    print(f"[adatbazis] {mentve} uj hirdetes mentve ({len(allasok)} talalatbol).")
    return mentve


def _hirdetes_ment(db, allas: dict, szakma_id):
    """Egy hirdetés mentése duplikátum-ellenőrzéssel.
    None-t ad vissza, ha már megvolt (vagy nincs címe)."""
    cim = (allas.get("cim") or "").strip()
    if not cim:
        return None
    link = (allas.get("link") or "").strip()
    ceg_id = ceg_ment(allas.get("ceg", ""))

    # Duplikátum-ellenőrzés: link alapján; link nélkül cím + cég alapján
    if link:
        r = db.table("hirdetesek").select("id").eq("link", link).limit(1).execute()
    else:
        q = db.table("hirdetesek").select("id").eq("cim", cim)
        if ceg_id:
            q = q.eq("ceg_id", ceg_id)
        r = q.limit(1).execute()
    if r.data:
        return None

    forras = allas.get("forras_tipus", "egyeb")
    if forras not in ERVENYES_FORRAS_TIPUSOK:
        forras = "egyeb"

    sor = {
        "cim": cim,
        "ceg_id": ceg_id,
        "szakma_id": szakma_id,
        "helyszin": allas.get("helyszin", ""),
        "snippet": allas.get("snippet", ""),
        "link": link,
        "datum_szoveg": allas.get("datum", ""),
        "forras_tipus": forras,
        "bersav": allas.get("bersav", ""),
    }
    r = db.table("hirdetesek").insert(sor).execute()
    return r.data[0]["id"] if r.data else None


def _keszsegek_ment(db, hirdetes_id, keszsegek: list):
    """Készségek upsert (név egyedi) + kapcsolótábla feltöltése."""
    sorok = {}
    for k in keszsegek:
        nev = " ".join((k.get("nev") or "").split())
        if not nev or len(nev) > 80:
            continue
        tipus = k.get("tipus", "elvaras")
        if tipus not in ERVENYES_KESZSEG_TIPUSOK:
            tipus = "elvaras"
        sorok[nev] = {"nev": nev, "tipus": tipus}  # dict = név szerinti dedup
    if not sorok:
        return

    r = db.table("keszsegek").upsert(list(sorok.values()), on_conflict="nev").execute()
    kapcsolatok = [
        {"hirdetes_id": hirdetes_id, "keszseg_id": s["id"]}
        for s in (r.data or [])
    ]
    if kapcsolatok:
        db.table("hirdetes_keszseg").upsert(
            kapcsolatok, on_conflict="hirdetes_id,keszseg_id"
        ).execute()
