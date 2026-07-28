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

from backend.hirdetes_snapshot import (
    elemzesi_szoveg,
    forras_specifikus_validacios_hibak,
    snapshot_keszitese,
)
from backend.settings import get_settings

_kliens = None

ERVENYES_KESZSEG_TIPUSOK = ("elvaras", "feladat", "eszkoz", "soft", "iparag")
ERVENYES_FORRAS_TIPUSOK = ("portal", "ceges", "jooble", "eures")


def kliens():
    """Lusta kapcsolódás — csak az első használatkor csatlakozik,
    utána ugyanazt a klienst adja vissza."""
    global _kliens
    if _kliens is not None:
        return _kliens
    settings = get_settings()
    if not settings.database_ready:
        print("[adatbazis] FIGYELEM: SUPABASE_URL vagy SUPABASE_SECRET_KEY "
              "hianyzik a .env-bol — a mentes kimarad!")
        return None
    try:
        from supabase import create_client
        _kliens = create_client(
            settings.supabase_url,
            settings.supabase_secret_key,
        )
        return _kliens
    except Exception as e:
        print(f"[adatbazis] Kapcsolodas sikertelen: {e}")
        return None


# ── SZAKMA ───────────────────────────────────────────────────

def szakma_ment(szakma_info: dict):
    """Név alapján upsert; visszaadja a szakma id-jét (vagy None-t).
    KISBETŰ-NAGYBETŰ ÉRZÉKETLEN: ha a név már létezik más írásmóddal
    (pl. 'Bolti eladó' vs 'bolti eladó'), NEM hoz létre duplikátumot."""
    db = kliens()
    nev = (szakma_info.get("szakma") or "").strip()
    if not db or not nev:
        return None
    # Van-e már ilyen név bármilyen írásmóddal?
    r = db.table("szakmak").select("id").ilike("nev", nev).limit(1).execute()
    if r.data:
        return r.data[0]["id"]
    try:
        r = db.table("szakmak").insert(
            {
                "nev": nev,
                "kategoria": szakma_info.get("szakma_kategoria", ""),
            }
        ).execute()
        return r.data[0]["id"] if r.data else None
    except Exception:
        r = (
            db.table("szakmak")
            .select("id")
            .ilike("nev", nev)
            .limit(1)
            .execute()
        )
        if r.data:
            return r.data[0]["id"]
        raise


# ── CÉG + CÉGINFÓ-CACHE ──────────────────────────────────────

def ceg_ment(nev: str):
    db = kliens()
    nev = (nev or "").strip()
    if not db or not nev:
        return None
    regi = db.table("cegek").select("id").eq("nev", nev).limit(1).execute()
    if regi.data:
        return regi.data[0]["id"]
    try:
        uj = db.table("cegek").insert({"nev": nev}).execute()
        return uj.data[0]["id"] if uj.data else None
    except Exception:
        # Párhuzamos beszúrásnál az egyedi kulcs dönt; nem upsertelünk és
        # nem írjuk felül a már létező cégsort.
        regi = db.table("cegek").select("id").eq("nev", nev).limit(1).execute()
        if regi.data:
            return regi.data[0]["id"]
        raise


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


def _valos_hirdetes_datum(datum_szoveg: str, letrehozva: str) -> datetime.date:
    """A hirdetés VALÓDI feladási dátumát adja vissza -- nem azt, mikor
    kerültünk rá MI (letrehozva), hanem amit a forrás (Jooble/EURES) a
    hirdetés tényleges dátumaként ad. Enélkül egy régóta fent lévő, de
    csak most, először megtalált hirdetés tévesen "frissnek" tűnne.

    Formátumok, amiket a gyűjtők ma mentenek:
      - Jooble: "ÉÉÉÉ-HH-NN" (scripts/jooble_gyujto.py)
      - EURES:  "ÉÉÉÉ.HH.NN." (utils/eures.py, _datum())

    Ha egyik sem értelmezhető (üres, hibás), a gyűjtési dátumra esünk
    vissza -- így legalább egy hozzávetőleges sorrend marad, nem esik ki
    a hirdetés a rangsorból pusztán egy hiányzó dátum miatt.
    """
    szoveg = (datum_szoveg or "").strip()
    for minta in ("%Y-%m-%d", "%Y.%m.%d.", "%Y.%m.%d"):
        try:
            return datetime.datetime.strptime(szoveg, minta).date()
        except ValueError:
            continue
    try:
        return datetime.datetime.fromisoformat(
            (letrehozva or "").replace("Z", "+00:00")
        ).date()
    except (ValueError, TypeError):
        return datetime.date.min


def friss_hirdetesek(
    szakma_nev: str,
    helyszin: str = "",
    max_nap: int = 30,
    limit: int = 15,
    *,
    elemzeshez: bool = False,
) -> list:
    """DB-FIRST: friss hirdetések a SAJÁT adatbázisunkból az adott szakmához.
    Ha van elég, nem kell internetes keresés — gyorsabb és ingyenes.

    FONTOS: a végleges sorrend a hirdetés VALÓDI feladási dátuma szerint
    készül (lásd _valos_hirdetes_datum()), nem a mi gyűjtési időbélyegünk
    szerint -- egy csak most megtalált, de régóta fent lévő hirdetés ne
    előzzön meg egy ténylegesen frissebb találatot.
    """
    db = kliens()
    if not db or not szakma_nev:
        return []
    try:
        r = db.table("szakmak").select("id").ilike("nev", szakma_nev.strip()).limit(1).execute()
        if not r.data:
            return []
        szakma_id = r.data[0]["id"]

        hatar = (datetime.datetime.now(datetime.timezone.utc)
                 - datetime.timedelta(days=max_nap)).isoformat()
        q = (db.table("hirdetesek")
               .select("id, cim, snippet, link, helyszin, datum_szoveg, bersav, forras_tipus, ceg_id, letrehozva")
               .eq("szakma_id", szakma_id)
               .gte("letrehozva", hatar))
        if helyszin:
            q = q.ilike("helyszin", f"%{helyszin}%")
        # Szélesebb jelölt-kört kérünk le, mint amennyit végül visszaadunk --
        # a VALÓDI dátum szerinti sorrendet csak ezután, Pythonban állítjuk
        # be, így a ténylegesen legfrissebbek nem eshetnek ki a jelöltek
        # közül pusztán a gyűjtési sorrend miatt.
        r = (q.order("letrehozva", desc=True)
              .limit(max(limit * 5, 50))
              .execute())
        sorok = r.data or []
        snapshotok = snapshot_kapuk_hirdetesekhez(
            db,
            [s.get("id") for s in sorok],
            elemzeshez=elemzeshez,
        )
        sorok = [s for s in sorok if s.get("id") in snapshotok]
        sorok.sort(
            key=lambda s: _valos_hirdetes_datum(s.get("datum_szoveg"), s.get("letrehozva")),
            reverse=True,
        )
        sorok = sorok[:limit]

        # Cégnevek egyetlen lekérdezéssel
        ceg_idk = list({s["ceg_id"] for s in sorok if s.get("ceg_id")})
        cegnev = {}
        if ceg_idk:
            rc = db.table("cegek").select("id, nev").in_("id", ceg_idk).execute()
            cegnev = {c["id"]: c["nev"] for c in (rc.data or [])}

        allasok = []
        for s in sorok:
            snapshot = snapshotok[s["id"]]
            allasok.append({
                "id": s.get("id"),
                "cim": s.get("cim", ""),
                "ceg": cegnev.get(s.get("ceg_id"), ""),
                # Elemzéskor kizárólag a validált, teljes nyers szöveg
                # használható. Listázáskor maradhat a rövid megjelenítési
                # kivonat, de a kapuállapotot továbbadjuk a hívónak.
                "snippet": (
                    elemzesi_szoveg(snapshot.get("raw_szoveg", ""))
                    if elemzeshez
                    else s.get("snippet", "")
                ),
                "link": s.get("link", ""),
                "helyszin": s.get("helyszin", ""),
                "datum": s.get("datum_szoveg", ""),
                "bersav": s.get("bersav", ""),
                "forras_tipus": s.get("forras_tipus", "egyeb"),
                "snapshot_id": snapshot.get("id"),
                "validacios_allapot": snapshot.get(
                    "validacios_allapot",
                    "legacy",
                ),
                "listazasra_alkalmas": snapshot.get(
                    "listazasra_alkalmas",
                    True,
                ),
                "szoveg_minoseg": snapshot.get("szoveg_minoseg"),
                "elemzesre_alkalmas": snapshot.get(
                    "elemzesre_alkalmas",
                    False,
                ),
                "legacy_snapshot_nelkuli": snapshot.get(
                    "legacy_snapshot_nelkuli",
                    False,
                ),
                "adatbazisbol": True,   # jelzés: ezt NEM kell újra menteni
            })
        return allasok
    except Exception as e:
        print(f"[adatbazis] Friss hirdetesek lekerdezese hiba: {e}")
        return []


def keszsegek_hirdetesekhez(hirdetes_idk: list) -> dict:
    """Több hirdetéshez EGYETLEN lekérdezéssel megadja a hozzájuk mentett
    készségeket (a hirdetes_keszseg kapcsolótáblán át).

    Visszatérés: {hirdetes_id: ["pénztárgép kezelése", "HACCP", ...], ...}
    Ez a determinisztikus (nem AI-alapú) egyezés-számoláshoz kell — a
    készségek MÁR el vannak mentve gyűjtéskor, itt csak lekérdezzük őket."""
    db = kliens()
    idk = [i for i in (hirdetes_idk or []) if i]
    if not db or not idk:
        return {}
    try:
        idk = sorted(elemzesre_alkalmas_hirdetes_idk(db, idk))
        if not idk:
            return {}
        r = (db.table("hirdetes_keszseg")
               .select(
                   "hirdetes_id,snapshot_id,feldolgozo_verzio,"
                   "forras_bizonyitek,forras_bizonyitek_kezdete,"
                   "forras_bizonyitek_vege,keszsegek(nev)"
               )
               .in_("hirdetes_id", idk)
               .execute())
        eredmeny: dict = {}
        for sor in hiteles_szarmasztott_sorok_hirdetesekhez(
            db,
            r.data or [],
        ):
            hid = sor.get("hirdetes_id")
            nev = (sor.get("keszsegek") or {}).get("nev")
            if hid and nev:
                eredmeny.setdefault(hid, []).append(nev)
        return eredmeny
    except Exception as e:
        print(f"[adatbazis] Keszsegek-hirdetesekhez lekerdezes hiba: {e}")
        return {}


def osszes_sor(tabla: str, oszlopok: str) -> list:
    """MINDEN sor lekérése lapozva — a Supabase egy hívásban max 1000-et ad!"""
    db = kliens()
    if not db:
        return []
    gyujto, start = [], 0
    while True:
        r = (db.table(tabla).select(oszlopok)
               .order("id").range(start, start + 999).execute())
        adag = r.data or []
        gyujto.extend(adag)
        if len(adag) < 1000:
            return gyujto
        start += 1000


# Kézi összevonások a névegyesítéshez: (ebből) -> (ebbe). Bővíthető bátran.
KEZI_OSSZEVONAS = {
    "Python programozás": "Python fejlesztés",
    "Java programozás": "Java",
    "fullstack fejlesztés": "full-stack fejlesztés",
    "full stack fejlesztés": "full-stack fejlesztés",
    "angol nyelv": "angol nyelvtudás",
    "angol nyelvismeret": "angol nyelvtudás",
    "német nyelv": "német nyelvtudás",
    "német nyelvismeret": "német nyelvtudás",
}


def _nevkulcs(nev: str) -> str:
    """Összehasonlító kulcs: minden szóköz-, kötőjel-változat és kis-nagybetű
    különbség eltűnik (a tipográfiai – — ‐ jeleket is kezeli)."""
    import re as _re
    return _re.sub(r"[\s \-‐‑‒–—_/]+", "", (nev or "").lower())


def keszsegnev_normalizalas() -> int:
    """Automatikus névegyesítés: írásváltozatok + kézi lista. AI nélkül,
    determinisztikusan. A gyűjtő minden futás végén meghívja."""
    db = kliens()
    if not db:
        return 0
    try:
        from collections import Counter, defaultdict
        sorok = osszes_sor("keszsegek", "id, nev, kanonikus")
        aktualis = [(s.get("kanonikus") or s.get("nev") or "").strip() for s in sorok]

        csoportok = defaultdict(list)
        for c in aktualis:
            if c:
                csoportok[_nevkulcs(c)].append(c)

        terkep = {}
        for _, lista in csoportok.items():
            egyedi = set(lista)
            if len(egyedi) > 1:
                vegleges = Counter(lista).most_common(1)[0][0]
                for valtozat in egyedi:
                    if valtozat != vegleges:
                        terkep[valtozat] = vegleges

        for k, v in KEZI_OSSZEVONAS.items():
            if k not in terkep and k in aktualis:
                terkep[k] = v

        for rol, ra in terkep.items():
            db.table("keszsegek").update({"kanonikus": ra}).eq("kanonikus", rol).execute()
            db.table("keszsegek").update({"kanonikus": ra}).is_("kanonikus", "null").eq("nev", rol).execute()

        if terkep:
            print(f"[adatbazis] Nevegyesites: {len(terkep)} valtozat osszevonva.")
        return len(terkep)
    except Exception as e:
        print(f"[adatbazis] Nevegyesites hiba: {e}")
        return 0


def szakmak_lista() -> list:
    """Szakmák, amikről már van hirdetésünk (a Tanácsadó választójához)."""
    db = kliens()
    if not db:
        return []
    try:
        r = (db.table("v_szakma_attekintes")
               .select("szakma, hirdetesek_szama")
               .gt("hirdetesek_szama", 0)
               .order("hirdetesek_szama", desc=True).execute())
        return r.data or []
    except Exception as e:
        print(f"[adatbazis] Szakmalista hiba: {e}")
        return []


def kereslet_korkep() -> list:
    """📊 ÉLŐ KERESLET-MUTATÓ szakmánként, a saját napi gyűjtésünkből.

    Két 30 napos ablakot hasonlít össze:
      friss_30  = hirdetések az utolsó 30 napban
      elozo_30  = hirdetések az azt megelőző 30 napban
      cegek_30  = hány KÜLÖNBÖZŐ cég keres most
      trend     = változás %-ban (csak ha az előző ablakban volt elég adat)
    Kategória (determinisztikus):
      🔥 erős és növekvő | 📈 növekvő | ➡️ stabil | 📉 csökkenő | ⚠️ kevés adat
    """
    db = kliens()
    if not db:
        return []
    try:
        from datetime import datetime, timedelta, timezone

        most = datetime.now(timezone.utc)
        h30 = most - timedelta(days=30)
        h60 = most - timedelta(days=60)

        # Az utolsó 60 nap hirdetései, lapozva (Supabase 1000-es limit!)
        sorok, start = [], 0
        while True:
            r = (db.table("hirdetesek")
                   .select("id, szakma_id, ceg_id, letrehozva")
                   .gte("letrehozva", h60.isoformat())
                   .range(start, start + 999).execute())
            adag = r.data or []
            sorok.extend(adag)
            if len(adag) < 1000:
                break
            start += 1000
        engedelyezett = elemzesre_alkalmas_hirdetes_idk(
            db,
            [sor.get("id") for sor in sorok],
        )
        sorok = [
            sor for sor in sorok if sor.get("id") in engedelyezett
        ]

        _szsorok = db.table("szakmak").select("id, nev, kategoria").execute().data or []
        nevek = {s["id"]: s["nev"] for s in _szsorok}
        kategoriak = {s["id"]: (s.get("kategoria") or "Egyéb") for s in _szsorok}

        from collections import defaultdict
        gyujto = defaultdict(lambda: {"friss": 0, "elozo": 0, "cegek": set()})
        for s in sorok:
            szid = s.get("szakma_id")
            if not szid or szid not in nevek:
                continue
            try:
                mikor = datetime.fromisoformat(
                    s["letrehozva"].replace("Z", "+00:00"))
            except (ValueError, KeyError, AttributeError):
                continue
            if mikor >= h30:
                gyujto[szid]["friss"] += 1
                if s.get("ceg_id"):
                    gyujto[szid]["cegek"].add(s["ceg_id"])
            else:
                gyujto[szid]["elozo"] += 1

        eredmeny = []
        for szid, a in gyujto.items():
            trend = None
            if a["elozo"] >= 3:
                trend = round(100 * (a["friss"] - a["elozo"]) / a["elozo"])
            if a["friss"] < 5:
                kategoria = "⚠️ kevés adat"
            elif trend is None:
                # még nincs két teljes 30 napos ablak — trendet nem állítunk
                kategoria = ("🔥 élénk kereslet" if a["friss"] >= 20
                             else "➡️ mérsékelt kereslet")
            elif trend >= 25 and a["friss"] >= 10:
                kategoria = "🔥 erős és növekvő"
            elif trend >= 25:
                kategoria = "📈 növekvő"
            elif trend <= -25:
                kategoria = "📉 csökkenő"
            else:
                kategoria = "➡️ stabil"
            eredmeny.append({
                "szakma": nevek[szid],
                "szektor": kategoriak.get(szid, "Egyéb"),
                "friss_30": a["friss"],
                "elozo_30": a["elozo"],
                "cegek_30": len(a["cegek"]),
                "trend": trend,
                "kategoria": kategoria,
            })
        eredmeny.sort(key=lambda e: -e["friss_30"])
        return eredmeny
    except Exception as e:
        print(f"[adatbazis] Kereslet-korkep hiba: {e}")
        return []


def szakma_statisztika(szakma_nev: str) -> dict:
    """Egy szakma piaci képe a saját adatainkból: hirdetésszám,
    leggyakoribb elvárások (százalékkal), bérinfók."""
    db = kliens()
    if not db or not szakma_nev:
        return {}
    try:
        r = db.table("szakmak").select("id").ilike("nev", szakma_nev.strip()).limit(1).execute()
        if not r.data:
            return {}
        szid = r.data[0]["id"]

        hirdetesek, kezdet = [], 0
        while True:
            valasz = (
                db.table("hirdetesek")
                .select("id,bersav")
                .eq("szakma_id", szid)
                .order("id")
                .range(kezdet, kezdet + 999)
                .execute()
            )
            adag = valasz.data or []
            hirdetesek.extend(adag)
            if len(adag) < 1000:
                break
            kezdet += 1000

        engedelyezett = elemzesre_alkalmas_hirdetes_idk(
            db,
            [sor.get("id") for sor in hirdetesek],
        )
        hirdetesek = [
            sor for sor in hirdetesek if sor.get("id") in engedelyezett
        ]

        from collections import Counter

        gyakorisag: Counter = Counter()
        engedelyezett_lista = sorted(engedelyezett)
        for kezdet in range(0, len(engedelyezett_lista), 100):
            kapcsolatok = (
                db.table("hirdetes_keszseg")
                .select(
                    "hirdetes_id,snapshot_id,feldolgozo_verzio,"
                    "forras_bizonyitek,forras_bizonyitek_kezdete,"
                    "forras_bizonyitek_vege,keszsegek(nev,tipus)"
                )
                .in_(
                    "hirdetes_id",
                    engedelyezett_lista[kezdet : kezdet + 100],
                )
                .execute()
                .data
                or []
            )
            for kapcsolat in hiteles_szarmasztott_sorok_hirdetesekhez(
                db,
                kapcsolatok,
            ):
                keszseg = kapcsolat.get("keszsegek") or {}
                nev = keszseg.get("nev")
                if nev:
                    gyakorisag[(nev, keszseg.get("tipus") or "elvaras")] += 1

        darab = len(hirdetesek)
        keszsegek = [
            {
                "keszseg": nev,
                "tipus": tipus,
                "elofordulas": elofordulas,
                "hirdetesek_szazaleka": round(
                    100 * elofordulas / max(darab, 1),
                    1,
                ),
            }
            for (nev, tipus), elofordulas in gyakorisag.most_common(25)
        ]

        return {
            "hirdetesek_szama": darab,
            "keszsegek": keszsegek,
            "bersavok": [
                sor["bersav"]
                for sor in hirdetesek
                if sor.get("bersav")
            ][:30],
        }
    except Exception as e:
        print(f"[adatbazis] Szakma-statisztika hiba: {e}")
        return {}


def szakma_atjaras(szakma_nev: str, top_n: int = 5) -> list:
    """ÁTJÁRÁSI TÉRKÉP: mely szakmákba vihető át a tudás?
    Készség-átfedést számol a kiválasztott és az összes többi szakma között,
    kizárólag a saját adatbázisunk hirdetéseiből."""
    db = kliens()
    if not db or not szakma_nev:
        return []
    try:
        from collections import defaultdict

        szakmak = db.table("szakmak").select("id,nev").execute().data or []
        szakma_nevek = {sor["id"]: sor["nev"] for sor in szakmak}
        alap_id = next(
            (
                azonosito
                for azonosito, nev in szakma_nevek.items()
                if nev.lower() == szakma_nev.lower()
            ),
            None,
        )
        if not alap_id:
            return []

        snapshot_sorok, kezdet = [], 0
        while True:
            valasz = (
                db.table("hirdetes_snapshot")
                .select(
                    "id,hirdetes_id,forras_tipus,forras_azonosito,"
                    "forras_szoveg_mezo,raw_payload,raw_szoveg,"
                    "szoveg_minoseg,"
                    "validacios_allapot,listazasra_alkalmas,"
                    "elemzesre_alkalmas,begyujtve"
                )
                .order("id")
                .range(kezdet, kezdet + 999)
                .execute()
            )
            adag = valasz.data or []
            snapshot_sorok.extend(adag)
            if len(adag) < 1000:
                break
            kezdet += 1000
        minden_hirdetes_id = [
            sor.get("hirdetes_id")
            for sor in snapshot_sorok
            if sor.get("hirdetes_id")
        ]
        snapshotok = snapshotok_kapuval(
            snapshot_sorok,
            minden_hirdetes_id,
            elemzeshez=True,
        )
        hirdetes_idk = sorted(snapshotok)

        hirdetes_szakma = {}
        for kezdet in range(0, len(hirdetes_idk), 200):
            sorok = (
                db.table("hirdetesek")
                .select("id,szakma_id")
                .in_(
                    "id",
                    hirdetes_idk[kezdet : kezdet + 200],
                )
                .execute()
                .data
                or []
            )
            hirdetes_szakma.update(
                {
                    sor["id"]: sor.get("szakma_id")
                    for sor in sorok
                    if sor.get("szakma_id")
                }
            )

        keszsegek: dict[int, set[str]] = defaultdict(set)
        for kezdet in range(0, len(hirdetes_idk), 50):
            kapcsolatok = (
                db.table("hirdetes_keszseg")
                .select(
                    "hirdetes_id,snapshot_id,feldolgozo_verzio,"
                    "forras_bizonyitek,forras_bizonyitek_kezdete,"
                    "forras_bizonyitek_vege,"
                    "keszsegek(nev,kanonikus,fogalom)"
                )
                .in_(
                    "hirdetes_id",
                    hirdetes_idk[kezdet : kezdet + 50],
                )
                .execute()
                .data
                or []
            )
            for kapcsolat in hiteles_szarmasztott_sorok(
                kapcsolatok,
                snapshotok,
            ):
                szakma_id = hirdetes_szakma.get(
                    kapcsolat.get("hirdetes_id")
                )
                keszseg = kapcsolat.get("keszsegek") or {}
                fogalom = (
                    keszseg.get("fogalom")
                    or keszseg.get("kanonikus")
                    or keszseg.get("nev")
                )
                if szakma_id and fogalom:
                    keszsegek[szakma_id].add(fogalom.strip().lower())

        sajat = keszsegek.get(alap_id, set())
        if not sajat:
            return []

        eredmeny = []
        for masik_id, masik_keszsegek in keszsegek.items():
            if masik_id == alap_id or len(masik_keszsegek) < 5:
                continue
            kozos = sajat & masik_keszsegek
            if len(kozos) < 3:
                continue  # kevés közös adat = megbízhatatlan, inkább nem mutatjuk
            atfedes = round(100 * len(kozos) / len(masik_keszsegek))
            hianyzo = sorted(masik_keszsegek - sajat)[:3]
            eredmeny.append({
                "szakma": szakma_nevek.get(masik_id, ""),
                "atfedes": atfedes,
                "kozos": len(kozos),
                "hianyzo": hianyzo,
            })
        eredmeny.sort(key=lambda e: -e["atfedes"])
        return eredmeny[:top_n]
    except Exception as e:
        print(f"[adatbazis] Atjaras-szamitas hiba: {e}")
        return []


def ksh_kereset(szakma_nev: str):
    """Hivatalos KSH-átlagkereset a szakmához — a foglalkozásnevek
    szótő-egyezése alapján keresi meg a legjobban illő KSH-sort."""
    db = kliens()
    if not db or not szakma_nev:
        return None
    try:
        import re as _re
        r = (db.table("piaci_statisztikak")
               .select("megnevezes, ertek, idoszak")
               .eq("forras", "KSH mun0208").execute())

        def tovek(szoveg):
            return {w[:6] for w in _re.findall(r"\w+", szoveg.lower()) if len(w) > 3}

        fsz = tovek(szakma_nev)
        legjobb, pont = None, 0.0
        for s in (r.data or []):
            nsz = tovek(s.get("megnevezes") or "")
            if not nsz:
                continue
            kozos = len(fsz & nsz)
            if not kozos:
                continue
            p = kozos / len(fsz) + kozos / len(nsz)
            if p > pont:
                pont, legjobb = p, s
        return legjobb if pont >= 0.5 else None
    except Exception as e:
        print(f"[adatbazis] KSH-lekerdezes hiba: {e}")
        return None


def kepzesek_lekerdez(teruletek: list) -> list:
    """Képzések a Supabase 'kepzesek' táblájából, terület szerint."""
    db = kliens()
    if not db or not teruletek:
        return []
    try:
        r = (db.table("kepzesek").select("*")
               .in_("terulet", teruletek).eq("aktiv", True).execute())
        return r.data or []
    except Exception as e:
        print(f"[adatbazis] Kepzesek lekerdezese hiba: {e}")
        return []


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


def snapshot_kapuk_hirdetesekhez(
    db,
    hirdetes_idk: list,
    *,
    elemzeshez: bool,
) -> dict:
    """A legfrissebb snapshot minőségkapuja hirdetésenként.

    Előbb kiválasztjuk a legfrissebb snapshotot, és csak utána vizsgáljuk a
    kaput. Így egy új karanténos verziót nem fedhet el egy régebbi elfogadott
    verzió. Snapshot nélküli legacy hirdetés listázható, elemzéskor viszont
    mindig fail-closed módon kimarad.
    """

    idk = list(dict.fromkeys(i for i in (hirdetes_idk or []) if i))
    if not db or not idk:
        return {}

    snapshot_sorok: list[dict] = []
    for kezdet in range(0, len(idk), 200):
        lap = 0
        while True:
            valasz = (
                db.table("hirdetes_snapshot")
                .select(
                    "id,hirdetes_id,forras_tipus,forras_azonosito,"
                    "forras_szoveg_mezo,raw_payload,raw_szoveg,"
                    "szoveg_minoseg,validacios_allapot,"
                    "listazasra_alkalmas,elemzesre_alkalmas,begyujtve"
                )
                .in_("hirdetes_id", idk[kezdet : kezdet + 200])
                .order("begyujtve", desc=True)
                .order("id", desc=True)
                .range(lap, lap + 999)
                .execute()
            )
            adag = valasz.data or []
            snapshot_sorok.extend(adag)
            if len(adag) < 1000:
                break
            lap += 1000
    return snapshotok_kapuval(
        snapshot_sorok,
        idk,
        elemzeshez=elemzeshez,
        legacy_listazhato=not elemzeshez,
    )


def _snapshot_sorrendkulcs(snapshot: dict) -> tuple:
    """Stabil legfrissebb-sorrend: begyűjtési idő, majd identity id."""

    szoveg = str(snapshot.get("begyujtve") or "")
    try:
        idopont = datetime.datetime.fromisoformat(
            szoveg.replace("Z", "+00:00")
        )
        if idopont.tzinfo is None:
            idopont = idopont.replace(tzinfo=datetime.timezone.utc)
        ido = idopont.timestamp()
    except (TypeError, ValueError, OSError):
        ido = float("-inf")
    try:
        azonosito = int(snapshot.get("id") or 0)
    except (TypeError, ValueError):
        azonosito = 0
    return ido, azonosito


def legujabb_snapshotok(
    snapshot_sorok: list,
    hirdetes_idk: list | None = None,
) -> dict:
    """Minden hirdetéshez pontosan a legfrissebb snapshotot adja."""

    engedelyezett = (
        {i for i in hirdetes_idk or [] if i}
        if hirdetes_idk is not None
        else None
    )
    eredmeny: dict = {}
    for sor in sorted(
        snapshot_sorok or [],
        key=_snapshot_sorrendkulcs,
        reverse=True,
    ):
        hirdetes_id = sor.get("hirdetes_id")
        if not hirdetes_id:
            continue
        if engedelyezett is not None and hirdetes_id not in engedelyezett:
            continue
        eredmeny.setdefault(hirdetes_id, sor)
    return eredmeny


def snapshotok_kapuval(
    snapshot_sorok: list,
    hirdetes_idk: list,
    *,
    elemzeshez: bool,
    legacy_listazhato: bool = False,
) -> dict:
    """Legfrissebb snapshot kiválasztása, majd a kért kapu alkalmazása."""

    idk = list(dict.fromkeys(i for i in hirdetes_idk or [] if i))
    legujabb = legujabb_snapshotok(snapshot_sorok, idk)
    kapu = "elemzesre_alkalmas" if elemzeshez else "listazasra_alkalmas"
    eredmeny = {
        hirdetes_id: snapshot
        for hirdetes_id, snapshot in legujabb.items()
        if snapshot.get(kapu) is True
        and not forras_specifikus_validacios_hibak(snapshot)
    }
    if legacy_listazhato and not elemzeshez:
        for hirdetes_id in idk:
            if hirdetes_id not in legujabb:
                eredmeny[hirdetes_id] = {
                    "id": None,
                    "hirdetes_id": hirdetes_id,
                    "szoveg_minoseg": "legacy_snapshot_nelkuli",
                    "validacios_allapot": "legacy",
                    "listazasra_alkalmas": True,
                    "elemzesre_alkalmas": False,
                    "legacy_snapshot_nelkuli": True,
                }
    return eredmeny


def hiteles_szarmasztott_sorok(
    sorok: list,
    snapshotok: dict,
) -> list:
    """Csak a legfrissebb, alkalmas snapshotból bizonyítható V2 sorok.

    A ``hirdetes_id`` önmagában soha nem elég: a sor snapshot-azonosítója
    egyezzen a legfrissebb elfogadott snapshotéval, legyen feldolgozóverzió,
    és a bizonyíték pontosan a snapshot nyers szövegének megadott szelete
    legyen. A régi, provenance nélküli sorok ezért később sem válhatnak
    hitelessé.
    """

    eredmeny: list[dict] = []
    for sor in sorok or []:
        snapshot = snapshotok.get(sor.get("hirdetes_id"))
        if not snapshot or sor.get("snapshot_id") != snapshot.get("id"):
            continue
        verzio = sor.get("feldolgozo_verzio")
        bizonyitek = sor.get("forras_bizonyitek")
        kezdet = sor.get("forras_bizonyitek_kezdete")
        veg = sor.get("forras_bizonyitek_vege")
        raw_szoveg = snapshot.get("raw_szoveg")
        if not isinstance(verzio, str) or not verzio.strip():
            continue
        if not isinstance(bizonyitek, str) or not bizonyitek:
            continue
        if not isinstance(kezdet, int) or not isinstance(veg, int):
            continue
        if not isinstance(raw_szoveg, str):
            continue
        if kezdet < 0 or veg <= kezdet or veg > len(raw_szoveg):
            continue
        if raw_szoveg[kezdet:veg] != bizonyitek:
            continue
        eredmeny.append(sor)
    return eredmeny


def hiteles_szarmasztott_sorok_hirdetesekhez(
    db,
    sorok: list,
) -> list:
    """Adatbázisból feloldott központi provenance-kapu."""

    hirdetes_idk = [sor.get("hirdetes_id") for sor in sorok or []]
    snapshotok = snapshot_kapuk_hirdetesekhez(
        db,
        hirdetes_idk,
        elemzeshez=True,
    )
    return hiteles_szarmasztott_sorok(sorok, snapshotok)


def elemzesre_alkalmas_hirdetes_idk(db, hirdetes_idk: list) -> set:
    """Központi, fail-closed elemzési kapu ATS-hez és karrierúthoz."""

    return set(
        snapshot_kapuk_hirdetesekhez(
            db,
            hirdetes_idk,
            elemzeshez=True,
        )
    )


# ── HIRDETÉSEK + KÉSZSÉGEK MENTÉSE ───────────────────────────

def gyujtes_mentese(szakma_info: dict, allasok: list, keszsegek_per_allas: list = None) -> int:
    """Auditált forrásgyűjtés eredményeit menti.

    keszsegek_per_allas: az allasok listával párhuzamos lista, elemei
    [{"nev": "...", "tipus": "elvaras"}, ...] alakúak.

    Provenance nélküli élő vagy mock találatnál még a szakma táblához sem
    írunk. A felhasználói keresés nem adatgyűjtő csatorna.

    Hibatűrő: egy auditált forráselem hibája a többit nem állítja meg.
    Visszaadja az ÚJ (nem duplikátum) hirdetések számát."""
    if not allasok:
        return 0
    if not keszsegek_per_allas:
        keszsegek_per_allas = [[] for _ in allasok]

    auditalthato = []
    for allas, keszsegek in zip(allasok, keszsegek_per_allas):
        snapshot = _snapshot_keszitese_allasbol(allas)
        if snapshot is None:
            print(
                "[adatbazis] Provenance nelkuli hirdetes nem kerul "
                "adatbazisba."
            )
            continue
        auditalthato.append((allas, keszsegek, snapshot))
    if not auditalthato:
        return 0

    db = kliens()
    if not db:
        return 0

    szakma_id = None
    try:
        szakma_id = szakma_ment(szakma_info)
    except Exception as e:
        print(f"[adatbazis] Szakma mentes hiba: {e}")

    mentve = 0
    for allas, keszsegek, snapshot in auditalthato:
        try:
            tarolt_snapshot = _snapshot_mentese(db, snapshot)
            if not tarolt_snapshot.get("listazasra_alkalmas"):
                print(
                    "[adatbazis] Karanten snapshot: "
                    f"{tarolt_snapshot.get('validacios_hibak') or []}"
                )
                continue

            hirdetes_id, uj_hirdetes = _hirdetes_ment(db, allas, szakma_id)
            if hirdetes_id is None:
                continue
            _snapshot_hirdeteshez_kapcsolasa(
                db,
                tarolt_snapshot,
                hirdetes_id,
            )
            if uj_hirdetes:
                mentve += 1
            if (
                uj_hirdetes
                and tarolt_snapshot.get("elemzesre_alkalmas") is True
                and keszsegek
            ):
                _keszsegek_ment(
                    db,
                    hirdetes_id,
                    keszsegek,
                    snapshot=tarolt_snapshot,
                )
        except Exception as e:
            print(f"[adatbazis] Hirdetes mentes hiba: {e}")

    print(
        f"[adatbazis] {mentve} uj hirdetes mentve "
        f"({len(auditalthato)} auditalthato talalatbol)."
    )
    return mentve


def _snapshot_keszitese_allasbol(allas: dict) -> dict | None:
    """A gyűjtő privát, nyers metaadataiból audit-snapshot készül."""

    meta = allas.get("_snapshot")
    if not isinstance(meta, dict):
        return None
    return snapshot_keszitese(
        forras_tipus=allas.get("forras_tipus", "egyeb"),
        forras_azonosito=meta.get("forras_azonosito", ""),
        forras_url=meta.get("forras_url"),
        keresesi_kulcsszo=meta.get("keresesi_kulcsszo"),
        forras_szoveg_mezo=meta.get("forras_szoveg_mezo", ""),
        raw_payload=meta.get("raw_payload"),
        raw_szoveg=meta.get("raw_szoveg", ""),
        szoveg_minoseg=meta.get("szoveg_minoseg", "ismeretlen"),
        cim=allas.get("cim", ""),
        nyelv=meta.get("nyelv"),
        gyujto=meta.get("gyujto_verzio", "ismeretlen"),
        gyujtesi_futas=meta.get("gyujtesi_futas", "ismeretlen"),
    )


def _snapshot_mentese(db, snapshot: dict) -> dict:
    """Insert-only mentés; azonos tartalmat nem írunk felül."""

    def _letezo():
        valasz = (
            db.table("hirdetes_snapshot")
            .select("*")
            .eq("forras_tipus", snapshot["forras_tipus"])
            .eq("forras_azonosito", snapshot["forras_azonosito"])
            .eq("raw_payload_sha256", snapshot["raw_payload_sha256"])
            .limit(1)
            .execute()
        )
        return (valasz.data or [None])[0]

    regi = _letezo()
    if regi:
        return regi
    try:
        valasz = db.table("hirdetes_snapshot").insert(snapshot).execute()
        if valasz.data:
            return valasz.data[0]
    except Exception:
        # Párhuzamos gyűjtők ugyanazt a hash-t egyszerre láthatják újnak.
        # Az egyedi index dönt; ütközés után csak visszaolvassuk a nyertest.
        regi = _letezo()
        if regi:
            return regi
        raise
    raise RuntimeError("A hirdetes_snapshot beszurasa nem adott vissza sort.")


def _snapshot_hirdeteshez_kapcsolasa(
    db,
    snapshot: dict,
    hirdetes_id: int,
) -> None:
    """Csak az üres kapcsolat tölthető ki; meglévőt nem írunk felül."""

    jelenlegi = snapshot.get("hirdetes_id")
    if jelenlegi == hirdetes_id:
        return
    if jelenlegi is not None:
        print(
            "[adatbazis] Snapshot mar masik hirdeteshez kapcsolodik; "
            "a regi kapcsolat valtozatlan marad."
        )
        return
    (
        db.table("hirdetes_snapshot")
        .update({"hirdetes_id": hirdetes_id})
        .eq("id", snapshot["id"])
        .is_("hirdetes_id", "null")
        .execute()
    )


def _hirdetes_ment(db, allas: dict, szakma_id):
    """Egy hirdetés mentése duplikátum-ellenőrzéssel.
    ``(id, új-e)`` párt ad; meglévő sort soha nem ír felül."""
    cim = (allas.get("cim") or "").strip()
    if not cim:
        return None, False
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
        return r.data[0]["id"], False

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
    return (r.data[0]["id"], True) if r.data else (None, False)


def _keszsegek_ment(
    db,
    hirdetes_id,
    keszsegek: list,
    *,
    snapshot: dict | None = None,
):
    """Bizonyítható V2 készségkapcsolatok insert-only mentése.

    A legacy hívók snapshot és pontos forrásbizonyíték nélkül nem hozhatnak
    létre új, hiteles sort. Ez szándékos fail-closed viselkedés.
    """

    if (
        not snapshot
        or snapshot.get("hirdetes_id") not in (None, hirdetes_id)
        or snapshot.get("elemzesre_alkalmas") is not True
        or not snapshot.get("id")
    ):
        return 0
    sorok = {}
    for k in keszsegek:
        nev = " ".join((k.get("nev") or "").split())
        if not nev or len(nev) > 80:
            continue
        tipus = k.get("tipus", "elvaras")
        if tipus not in ERVENYES_KESZSEG_TIPUSOK:
            tipus = "elvaras"
        bizonyitek = {
            "snapshot_id": snapshot["id"],
            "feldolgozo_verzio": k.get("feldolgozo_verzio"),
            "forras_bizonyitek": k.get("forras_bizonyitek"),
            "forras_bizonyitek_kezdete": k.get(
                "forras_bizonyitek_kezdete"
            ),
            "forras_bizonyitek_vege": k.get("forras_bizonyitek_vege"),
        }
        ellenorzo_sor = {"hirdetes_id": hirdetes_id, **bizonyitek}
        if not hiteles_szarmasztott_sorok(
            [ellenorzo_sor],
            {hirdetes_id: snapshot},
        ):
            continue
        sorok[nev] = {
            "nev": nev,
            "tipus": tipus,
            "_bizonyitek": bizonyitek,
        }
    if not sorok:
        return 0

    nevek = list(sorok)
    regi = (
        db.table("keszsegek")
        .select("id,nev")
        .in_("nev", nevek)
        .execute()
        .data
        or []
    )
    regi_nevek = {sor["nev"] for sor in regi}
    ujak = [
        {
            "nev": sorok[nev]["nev"],
            "tipus": sorok[nev]["tipus"],
        }
        for nev in nevek
        if nev not in regi_nevek
    ]
    if ujak:
        try:
            db.table("keszsegek").insert(ujak).execute()
        except Exception:
            # Párhuzamos beszúrás esetén visszaolvassuk az egyedi kulcs
            # nyerteseit; meglévő készségsort nem írunk felül.
            pass
    r = (
        db.table("keszsegek")
        .select("id,nev")
        .in_("nev", nevek)
        .execute()
    )
    kapcsolatok = [
        {
            "hirdetes_id": hirdetes_id,
            "keszseg_id": s["id"],
            **sorok[s["nev"]]["_bizonyitek"],
        }
        for s in (r.data or [])
    ]
    if kapcsolatok:
        db.table("hirdetes_keszseg").insert(kapcsolatok).execute()
    return len(kapcsolatok)
