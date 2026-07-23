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


def friss_hirdetesek(szakma_nev: str, helyszin: str = "",
                     max_nap: int = 30, limit: int = 15) -> list:
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
            allasok.append({
                "id": s.get("id"),
                "cim": s.get("cim", ""),
                "ceg": cegnev.get(s.get("ceg_id"), ""),
                "snippet": s.get("snippet", ""),
                "link": s.get("link", ""),
                "helyszin": s.get("helyszin", ""),
                "datum": s.get("datum_szoveg", ""),
                "bersav": s.get("bersav", ""),
                "forras_tipus": s.get("forras_tipus", "egyeb"),
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
        r = (db.table("hirdetes_keszseg")
               .select("hirdetes_id, keszsegek(nev)")
               .in_("hirdetes_id", idk)
               .execute())
        eredmeny: dict = {}
        for sor in (r.data or []):
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
                   .select("szakma_id, ceg_id, letrehozva")
                   .gte("letrehozva", h60.isoformat())
                   .range(start, start + 999).execute())
            adag = r.data or []
            sorok.extend(adag)
            if len(adag) < 1000:
                break
            start += 1000

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

        rh = db.table("hirdetesek").select("id", count="exact").eq("szakma_id", szid).execute()
        rk = (db.table("v_szakma_keszsegek")
                .select("keszseg, tipus, elofordulas, hirdetesek_szazaleka")
                .eq("szakma_id", szid)
                .order("elofordulas", desc=True).limit(25).execute())
        rb = (db.table("hirdetesek").select("bersav")
                .eq("szakma_id", szid).neq("bersav", "").limit(30).execute())

        return {
            "hirdetesek_szama": rh.count or 0,
            "keszsegek": rk.data or [],
            "bersavok": [s["bersav"] for s in (rb.data or []) if s.get("bersav")],
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

        # A FOGALOM-nézet összes sora, lapozva (gyűjtőfogalmak szintjén hasonlítunk!)
        sorok, start = [], 0
        while True:
            r = (db.table("v_szakma_fogalmak")
                   .select("szakma, fogalom, hirdetesek_szazaleka")
                   .order("szakma_id").order("fogalom")
                   .range(start, start + 999).execute())
            adag = r.data or []
            sorok.extend(adag)
            if len(adag) < 1000:
                break
            start += 1000

        # Szakmánként a jellemző fogalmak (ami a hirdetések min. 3%-ában kell)
        keszsegek = defaultdict(dict)
        for s in sorok:
            if (s.get("hirdetesek_szazaleka") or 0) >= 3:
                keszsegek[s["szakma"]][s["fogalom"]] = s["hirdetesek_szazaleka"]

        alap = next((n for n in keszsegek if n.lower() == szakma_nev.lower()), None)
        if not alap:
            return []
        sajat = set(keszsegek[alap])

        eredmeny = []
        for masik, mk in keszsegek.items():
            if masik == alap or len(mk) < 5:
                continue
            kozos = sajat & set(mk)
            if len(kozos) < 3:
                continue  # kevés közös adat = megbízhatatlan, inkább nem mutatjuk
            atfedes = round(100 * len(kozos) / len(mk))
            hianyzo = sorted(set(mk) - sajat, key=lambda k: -mk[k])[:3]
            eredmeny.append({
                "szakma": masik,
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
