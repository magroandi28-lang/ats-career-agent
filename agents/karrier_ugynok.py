# -*- coding: utf-8 -*-
# Karrier Ügynök Ágens - agents/karrier_ugynok.py

import anthropic
import requests
import os
import re
import json
import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from utils.adatbazis import (
    gyujtes_mentese,
    ceginfo_cache_lekerdez,
    ceginfo_cache_ment,
)

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY")

# ── TESZT KAPCSOLÓ ───────────────────────────────────────────
# True  = mock adatok (ingyenes, teszteléshez)
# False = éles SerpAPI keresés
TESZT_MOD = False

# ── MOCK ADATOK ──────────────────────────────────────────────

MOCK_ALLASOK = {
    "bolti elado": [
        {
            "cim": "Bolti eladó / pénztáros",
            "ceg": "Penny Market Kft.",
            "snippet": "Keresünk bolti eladót budapesti üzletünkbe. Feladatok: készletgazdálkodás, pénztárgép kezelése, vevőkiszolgálás, árufeltöltés, HACCP előírások betartása.",
            "link": "https://www.profession.hu/allas/penny-market-bolti-elado",
            "helyszin": "Budapest"
        },
        {
            "cim": "Eladó munkatárs",
            "ceg": "Lidl Magyarország Bt.",
            "snippet": "Lidl üzletünkbe keresünk eladó munkatársat. Feladatok: kassza kezelés, árufeltöltés, készletezés, HACCP előírások. Versenyképes bér.",
            "link": "https://www.jobs.hu/allas/lidl-elado-munkatars",
            "helyszin": "Budapest"
        },
        {
            "cim": "Pénztáros",
            "ceg": "SPAR Magyarország Kft.",
            "snippet": "Pénztárost keresünk budapesti áruházunkba. Feladatok: pénztárgép kezelése, vevőkiszolgálás, készpénz- és bankkártyás fizetés kezelése.",
            "link": "https://www.profession.hu/allas/spar-penztaros",
            "helyszin": "Budapest"
        },
        {
            "cim": "Bolti eladó - élelmiszer",
            "ceg": "ALDI Magyarország",
            "snippet": "Élelmiszerbolti eladót keresünk. Feladatok: árufeltöltés, készletgazdálkodás, HACCP előírások betartása, vevőkiszolgálás, eladótér rendje.",
            "link": "https://www.jobs.hu/allas/aldi-bolti-elado",
            "helyszin": "Budapest"
        },
        {
            "cim": "Drogériai eladó",
            "ceg": "DM Kft.",
            "snippet": "Drogériai eladót keresünk. Feladatok: vevőtanácsadás, árufeltöltés, pénztárkezelés. Kozmetikai termékek ismerete előny.",
            "link": "https://www.profession.hu/allas/dm-drogeriai-elado",
            "helyszin": "Budapest"
        }
    ],
    "python fejleszto": [
        {
            "cim": "Python Backend Fejlesztő",
            "ceg": "TechSolutions Kft.",
            "snippet": "Python backend fejlesztőt keresünk. Elvárás: Python 3+, FastAPI vagy Django, PostgreSQL, Docker. Remote lehetőség.",
            "link": "https://www.profession.hu/allas/techsolutions-python",
            "helyszin": "Budapest"
        },
        {
            "cim": "Senior Python Developer",
            "ceg": "DataBridge Zrt.",
            "snippet": "Senior Python fejlesztőt keresünk. Elvárás: 3+ év Python, SQL, REST API, CI/CD. Vonzó bérezés.",
            "link": "https://www.jobs.hu/allas/databridge-senior-python",
            "helyszin": "Budapest"
        }
    ]
}

MOCK_CEGINFOK = {
    "Penny Market Kft.": {
        "leiras": "Nemzetközi kiskereskedelmi lánc, 1994 óta Magyarországon. 200+ üzlet az országban, stabil munkáltató.",
        "bersav": "280.000 - 350.000 Ft/hó",
        "fluktuacio": "Közepes",
        "velemenyek": "Stabil munkahely, rendszeres fizetés. Intenzív munkatempó de jó csapatszellem.",
        "figyelmeztetes": None,
        "meret": "Nagy cég, 5000+ alkalmazott"
    },
    "Lidl Magyarország Bt.": {
        "leiras": "Német diszkont lánc, erős HR kultúra, folyamatos terjeszkedés Magyarországon.",
        "bersav": "320.000 - 400.000 Ft/hó",
        "fluktuacio": "Alacsony",
        "velemenyek": "Versenyképes bérezés, karrierlehetőség. Szigorú szabályok, gyors tempó.",
        "figyelmeztetes": None,
        "meret": "Nagy cég, 3000+ alkalmazott"
    },
    "TechSolutions Kft.": {
        "leiras": "Magyar IT cég, szoftverfejlesztés és tanácsadás. 2010 óta működik.",
        "bersav": "600.000 - 900.000 Ft/hó",
        "fluktuacio": "Alacsony",
        "velemenyek": "Jó szakmai fejlődés, rugalmas munkaidő. Kisebb csapat, közvetlen kommunikáció.",
        "figyelmeztetes": None,
        "meret": "Kis-közepes cég, 50-100 fő"
    },
    "DataBridge Zrt.": {
        "leiras": "Adatelemzési és BI megoldások, 2015 óta. Növekvő fintech ügyfelekkel.",
        "bersav": "700.000 - 1.100.000 Ft/hó",
        "fluktuacio": "Közepes",
        "velemenyek": "Érdekes projektek, jó csapat. Néha magas nyomás határidők miatt.",
        "figyelmeztetes": None,
        "meret": "Közepes cég, 100-200 fő"
    }
}


# ── 1. SZAKMA FELISMERÉS ─────────────────────────────────────

def szakma_felismeres(cv_szoveg: str = "", szakma_megadva: str = "") -> dict:
    if szakma_megadva:
        forras = f"A jelölt megadta: {szakma_megadva}"
    else:
        forras = f"A jelölt CV-je:\n{cv_szoveg}"

    prompt = f"""Te egy tapasztalt magyar recruiter vagy.

{forras}

Válaszolj KIZÁRÓLAG JSON formátumban:

{{
  "szakma": "pontos szakma neve",
  "szakma_kategoria": "IT/Egészségügy/Kereskedelem/Ipar/Szolgáltatás/Egyéb",
  "tapasztalat_evek": 0,
  "tapasztalt_szakember": true,
  "utos_kulcsszavak": ["kulcsszó 1", "kulcsszó 2", "kulcsszó 3", "kulcsszó 4", "kulcsszó 5"],
  "ajanlott_cegek": ["Cég1", "Cég2", "Cég3", "Cég4", "Cég5"],
  "portfilio_ajanlott": false,
  "portfilio_indoklas": "Miért ajánlott vagy nem"
}}

Szabályok:
- tapasztalt_szakember: true ha 5+ év tapasztalat VAN
- portfilio_ajanlott: true ha 5+ év tapasztalat ÉS van miből portfóliót készíteni
- Eladónál kulcsszavak: készletgazdálkodás, pénztárgép kezelése, HACCP, vevőkiszolgálás
- IT-snél: Python, FastAPI, Docker, REST API, agilis módszertan
- ajanlott_cegek: 5 KONKRÉT, VALÓDI, MAGYARORSZÁGON működő cég, amelyik ezt a szakmát foglalkoztatja ÉS valószínűleg van karrier/állás oldala. Példák az elvre: bolti eladónál Aldi, Lidl, SPAR, Tesco, Penny; szoftverfejlesztőnél EPAM, Cisco, Ericsson, Continental, LogMeIn. A szakmához illő, ismert munkáltatókat adj."""

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )

    szoveg = response.content[0].text.strip()
    if "```json" in szoveg:
        szoveg = szoveg.split("```json")[1].split("```")[0].strip()
    elif "```" in szoveg:
        szoveg = szoveg.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(szoveg)
    except Exception:
        return {
            "szakma": szakma_megadva or "Ismeretlen",
            "tapasztalt_szakember": False,
            "portfilio_ajanlott": False,
            "utos_kulcsszavak": []
        }


# ── 2. ÁLLÁSKERESÉS ──────────────────────────────────────────

def oldal_letoltes(url: str) -> dict:
    """Letölti az oldalt, és visszaadja a tiszta szöveget ÉS a hirdetés-linkeket.

    Visszatérés: {"szoveg": "...", "linkek": [{"szoveg": "...", "url": "..."}]}
    A linkeket MÉG a tag-ek eldobása ELŐTT gyűjtjük ki, mert a get_text() a
    hivatkozásokat (href) eldobja — emiatt korábban minden állás a listázó-oldal
    linkjét kapta, és kereskedni kellett, melyik a tiéd.
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return {"szoveg": "", "linkek": []}
        soup = BeautifulSoup(r.text, "html.parser")

        # 1) ELŐSZÖR a konkrét hirdetés-linkeket gyűjtjük ki (a címke szövegével együtt)
        linkek = []
        latott_url = set()
        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            teljes = urljoin(url, href)
            if not teljes.lower().startswith("http"):
                continue
            # Csak álláshirdetésre utaló linkek (nem menü, nem általános oldal)
            if not re.search(r'/(allas|allasok|job|jobs|career|careers|karrier|'
                             r'position|positions|vacancy|vacancies|hirdetes|stelle)',
                             teljes.lower()):
                continue
            cimke = " ".join(a.get_text().split())[:120]
            if not cimke or len(cimke) < 3:
                continue
            if teljes in latott_url:
                continue
            latott_url.add(teljes)
            linkek.append({"szoveg": cimke, "url": teljes})
            if len(linkek) >= 40:
                break

        # 2) Most már jöhet a tag-tisztítás és a sima szöveg
        for t in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            t.decompose()
        szoveg = " ".join(soup.get_text(separator=" ").split())[:12000]
        return {"szoveg": szoveg, "linkek": linkek}
    except Exception:
        return {"szoveg": "", "linkek": []}


def allasok_kinyerese_oldalbol(szoveg: str, linkek: list, szakma: str, client) -> list:
    """A modell kiszedi a tiszta szövegből a konkrét, AKTUÁLIS állásokat (max 5/oldal),
    a lejárt hirdetéseket kihagyja, és — ha tudja — minden álláshoz a saját
    konkrét linkjét és dátumát párosítja a megadott link-listából."""
    if not szoveg or len(szoveg) < 100:
        return []

    if linkek:
        link_lista = "\n".join([f'- "{l["szoveg"]}" -> {l["url"]}' for l in linkek[:40]])
    else:
        link_lista = "(nincs kinyerhető konkrét link ezen az oldalon)"

    prompt = f"""Egy álláskereső/céges oldal szövegéből kell konkrét, AKTUÁLIS álláshirdetéseket kinyerned.

Keresett szakma: {szakma}
Mai dátum: {datetime.date.today().isoformat()}

AZ OLDAL SZÖVEGE:
{szoveg}

ELÉRHETŐ HIRDETÉS-LINKEK (a hirdetés címe -> a hozzá tartozó konkrét URL):
{link_lista}

Feladat: szedd ki a konkrét álláshirdetéseket (max 5 db, a legrelevánsabbakat a keresett szakmához).
CSAK valódi, konkrét állásokat adj vissza (cégnévvel) — NE kategóriákat, NE menüpontokat, NE általános szövegeket.

KÖTELEZŐ SZŰRÉS:
- HAGYD KI a lejárt / betöltött / archivált / már nem aktív hirdetéseket
  (jelek: "lejárt", "betöltött", "archivált", "az állás már nem elérhető", "expired", "no longer available", "no longer accepting").
- HAGYD KI a 2025-ös vagy korábbi dátumú hirdetéseket. Csak 2026-os VAGY dátum nélküli (de láthatóan aktuális) állás jöhet.
- Minden álláshoz párosítsd a fenti link-listából a hozzá tartozó KONKRÉT linket a hirdetés címe alapján.
  Ha egyetlen link sem tartozik egyértelműen az adott álláshoz, a "link" mező legyen üres string ("").
- Ha látsz dátumot a hirdetésnél (feladás/módosítás dátuma vagy év), írd a "datum" mezőbe (pl. "2026-05" vagy "2026").
  Ha nincs dátum, a "datum" legyen üres string ("").

Válaszolj KIZÁRÓLAG JSON-tömbként:
[
  {{"cim": "pozíció neve", "ceg": "cég neve", "snippet": "főbb feladatok/elvárások 1-2 mondatban", "helyszin": "város/kerület", "datum": "", "link": ""}}
]
Ha nincs aktuális, konkrét állás a szövegben, adj vissza üres tömböt: []"""
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5", max_tokens=1500, temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        t = resp.content[0].text.strip()
        if "```json" in t:
            t = t.split("```json")[1].split("```")[0].strip()
        elif "```" in t:
            t = t.split("```")[1].split("```")[0].strip()
        return json.loads(t)
    except Exception:
        return []


def _lejart_e(allas: dict) -> bool:
    """Biztonsági utószűrő: True, ha a hirdetés láthatóan lejárt/régi.
    Szándékosan ÓVATOS — inkább engedjen át egy bizonytalan állást, mint hogy
    egy jó hirdetést kidobjon (a céges oldalakon vannak nagyon jó állások!)."""
    # 1) Lejárt-jelző szavak a címben/leírásban/dátumban
    blob = f"{allas.get('cim','')} {allas.get('snippet','')} {allas.get('datum','')}".lower()
    lejart_jelek = [
        "lejárt", "lejart", "betöltött", "betoltott", "archivált", "archivalt",
        "már nem elérhető", "mar nem elerheto", "már nem aktív", "mar nem aktiv",
        "expired", "no longer available", "no longer accepting", "position closed"
    ]
    if any(jel in blob for jel in lejart_jelek):
        return True

    # 2) Évszám CSAK a datum mezőből (a snippetben sok más okból lehet évszám,
    #    pl. "2018–2024 tapasztalat" vagy "alapítva 2015" — azt NEM nézzük).
    jelen_ev = datetime.date.today().year
    datum = (allas.get("datum") or "")
    evek = re.findall(r"20\d{2}", datum)
    if evek and all(int(e) < jelen_ev for e in evek):
        return True

    return False


def allasok_keresese(szakma: str, helyszin: str = "Budapest", ajanlott_cegek: list = None) -> list:
    if TESZT_MOD:
        print("TESZT MOD - mock adatok")
        szakma_lower = szakma.lower()
        for kulcs, allasok in MOCK_ALLASOK.items():
            kulcs_szavak = kulcs.split()
            if any(szo in szakma_lower for szo in kulcs_szavak):
                print(f"Mock: {len(allasok)} allas")
                return allasok
        return list(MOCK_ALLASOK.values())[0]

    # ── Éles mód: SerpAPI forrás-keresés + SCRAPER ágens (konkrét állások) ──
    # Külön gyűjtjük a PORTÁL-forrásokat és a CÉGES oldalakat, hogy MINDKETTŐ
    # bekerüljön (a céges karrieroldalakon sokszor más állások vannak, mint a portálon).
    portal_linkek = []
    ceges_linkek = []
    latott = set()

    def _gyujt(query, hova, max_db):
        try:
            params = {"engine": "google", "q": query,
                      "api_key": SERPAPI_KEY, "hl": "hu", "gl": "hu", "num": 5}
            r = requests.get("https://serpapi.com/search", params=params, timeout=10)
            for item in r.json().get("organic_results", []):
                link = item.get("link", "")
                ll = link.lower()
                if re.search(r'\.(xlsx?|pdf|docx?|csv)(\?|$)', ll):
                    continue
                if any(x in ll for x in ["wikipedia", "jooble", "/szotar", "njt.hu",
                                         "torveny", "facebook.com", "linkedin.com"]):
                    continue
                if link and link not in latott:
                    latott.add(link)
                    hova.append(link)
                if len(hova) >= max_db:
                    break
        except Exception as e:
            print(f"Forras-kereses hiba: {e}")

    # Portál-forrás (1 állásportál-listázó – sok konkrét állást tartalmaz)
    _gyujt(f'site:profession.hu {szakma} {helyszin}', portal_linkek, 1)

    # CÉGES oldalak: a modell által javasolt cégek karrier/állás oldalát célozzuk.
    # Így tényleg a cégek SAJÁT oldaláról gyűjtünk (nem portálról).
    cegek = ajanlott_cegek or []
    for ceg in cegek[:5]:
        if len(ceges_linkek) >= 3:
            break
        _gyujt(f'{ceg} karrier állás {szakma}', ceges_linkek, 3)

    # Ha a céges keresés kevés oldalt hozott, kiegészítjük általános céges kereséssel
    if len(ceges_linkek) < 2:
        _gyujt(f'{szakma} állás {helyszin} karrier -site:profession.hu '
               f'-site:jooble.org -site:cvonline.hu -site:jobline.hu', ceges_linkek, 3)

    # Garantáltan vegyes – 1 portál + max 2 céges oldal (összesen max 3 forrás).
    # A forrás TÍPUSÁT is megőrizzük, mert a céges állásokra szigorúbb szabály vonatkozik (A opció).
    forras_sorrend = [(l, "portal") for l in portal_linkek[:1]]
    forras_sorrend += [(l, "ceges") for l in ceges_linkek[:2]]
    if len(forras_sorrend) < 3:
        for l in portal_linkek[1:]:
            forras_sorrend.append((l, "portal"))
            if len(forras_sorrend) >= 3:
                break

    # Scraper: a forrás-oldalakat letöltjük és kinyerjük a konkrét, aktuális állásokat.
    # A opció:
    #  - PORTÁL állás: bekerül; konkrét linkje ha van, különben a listázó-oldal (mint eddig).
    #  - CÉGES állás: CSAK akkor kerül be, ha VAN dátuma ÉS VAN konkrét linkje (különben kihagyjuk).
    #  - Lejárt hirdetést MINDKÉT forrásból kiszűrünk (modell + utószűrő).
    allasok = []
    elutasitott_ceges = 0
    for link, tipus in forras_sorrend[:3]:
        letoltve = oldal_letoltes(link)
        szoveg = letoltve.get("szoveg", "")
        oldal_linkek = letoltve.get("linkek", [])
        if not szoveg:
            continue
        kinyert = allasok_kinyerese_oldalbol(szoveg, oldal_linkek, szakma, client)
        for a in kinyert:
            # Lejárt szűrő minden forrásra
            if _lejart_e(a):
                continue
            konkret_link = (a.get("link") or "").strip()
            van_datum = bool((a.get("datum") or "").strip())

            if tipus == "ceges":
                # A opció: céges állás csak dátummal ÉS konkrét linkkel
                if not (van_datum and konkret_link):
                    elutasitott_ceges += 1
                    continue
                a["link"] = konkret_link
            else:
                # Portál: konkrét link ha van, különben a listázó-oldal (forrás)
                a["link"] = konkret_link or link

            a["forras_tipus"] = tipus
            a.setdefault("helyszin", helyszin)
            allasok.append(a)
        if len(allasok) >= 10:
            break

    print(f"Eles kereses (scraper): {len(allasok)} konkret, aktualis allas "
          f"({len(portal_linkek[:1])} portal + {len(ceges_linkek[:2])} ceges oldal); "
          f"ceges elutasitva (nincs datum/link): {elutasitott_ceges}")
    return allasok


# ── 3. CÉGINFÓ (csak kérésre hívódik, nem a run-ban) ─────────

def ceginfo_kereses(ceg_nev: str) -> dict:
    """
    TESZT_MOD = True  -> mock adat (ingyenes, azonnali)
    TESZT_MOD = False -> éles SerpAPI + Claude (ceginfo_agensek)
    """
    if TESZT_MOD:
        print(f"  Céginfó (MOCK): {ceg_nev}")
        if ceg_nev in MOCK_CEGINFOK:
            mock = dict(MOCK_CEGINFOK[ceg_nev])
        else:
            mock = {
                "leiras": "Teszt cég leírás.",
                "bersav": "Nincs megerősített adat",
                "fluktuacio": "Nincs megerősített adat",
                "velemenyek": "Nincs elérhető vélemény.",
                "figyelmeztetes": None,
                "meret": "Ismeretlen"
            }
        mock.setdefault("fluktuacio", "Nincs megerősített adat")
        return mock

    # Céginfó-CACHE: ha 30 napon belül már lekérdezte valaki ezt a céget,
    # az adatbázisból adjuk vissza — nincs újabb SerpAPI-költség.
    cache = ceginfo_cache_lekerdez(ceg_nev)
    if cache:
        return cache

    from agents.ceginfo_agensek import ceginfo_kereses as agensek_ceginfo
    info = agensek_ceginfo(ceg_nev)
    ceginfo_cache_ment(ceg_nev, info)
    return info


# ── 4. ATS DIAGNÓZIS ─────────────────────────────────────────

def ats_diagnozis(cv_szoveg: str, allasok: list, szakma_info: dict) -> dict:
    allasok_szoveg = "\n\n".join([
        f"Hirdetés {i+1} - {a['ceg']}:\n{a['snippet']}"
        for i, a in enumerate(allasok)
    ])

    prompt = f"""Te egy magyar ATS szakértő és recruiter vagy.

Szakma: {szakma_info.get('szakma', '')}

CV (a jelölt EREDETI, akár pongyola megfogalmazásában):
{cv_szoveg}

Álláshirdetések:
{allasok_szoveg}

FONTOS — jelentés alapján dolgozz, nem szó szerint:
- A jelölt sokszor laikusan fogalmaz. Ismerd fel a JELENTÉST, és a SZAKMAI megnevezést használd.
  Példák: "pénztárazás" / "kasszáztam" = "pénztárgép kezelése"; "áruk kirakása" / "árut pakoltam" = "árufeltöltés"; "rendrakás" = "üzlettér rendezése".
- Ha egy készség a CV-ben BÁRMILYEN szóval (akár pongyolán) szerepel, az MEGLÉVŐ — akkor is, ha a hirdetés más szót használ rá. Ilyenkor NE tedd a hiányzók közé.
- Egy adott készség VAGY meglévő, VAGY hiányzó lehet — SOHA mindkettő. Mielőtt egy szót hiányzónak jelölsz, ellenőrizd, hogy szinonimája nincs-e már a CV-ben.

Feladat:
1. Gyűjtsd ki a hirdetések szakmai elvárásait (szakmai néven).
2. Döntsd el jelentés alapján, melyik van már meg a CV-ben (bármilyen megfogalmazásban) → meglévő.
3. Ami valóban sehogy sem szerepel → hiányzó.

Válaszolj KIZÁRÓLAG JSON formátumban, a kulcsszavakat MINDIG szakmai néven:

{{
  "illeszkedes_szazalek": 65,
  "van_eselye": true,
  "hianyzo_kulcsszavak": [
    {{"szo": "HACCP előírások betartása", "hirdetesek_szama": 1, "fontos": true}}
  ],
  "meglevo_kulcsszavak": ["pénztárgép kezelése", "árufeltöltés", "vevőkiszolgálás"],
  "meglevo_erossegek": ["Erősség 1"],
  "fo_problema": "Miért szűri ki a robot",
  "kepzes_kell": false
}}

SZIGORÚ szabályok:
- SOHA ne adj helyszínt kulcsszóként (Budapest stb.).
- SOHA ne adj személyes tulajdonságot (megbízható stb.).
- Csak SZAKMAI kulcsszavak, MINDIG szakmai néven (a pongyola CV-szót is fordítsd át).
- Egy fogalom nem lehet egyszerre meglévő ÉS hiányzó.
- Hiányzó csak az lehet, aminek jelentése sehogy sem szerepel a CV-ben."""

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1000,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )

    szoveg = response.content[0].text.strip()
    if "```json" in szoveg:
        szoveg = szoveg.split("```json")[1].split("```")[0].strip()
    elif "```" in szoveg:
        szoveg = szoveg.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(szoveg)
    except Exception:
        return {
            "illeszkedes_szazalek": 50,
            "van_eselye": True,
            "hianyzo_kulcsszavak": [],
            "meglevo_kulcsszavak": [],
            "fo_problema": "",
            "kepzes_kell": False
        }


# ── 5. CV ÁTÍRÁS ─────────────────────────────────────────────

def cv_atiras(cv_szoveg: str, allas: dict, szakma_info: dict,
              diagnozis: dict = {}, ceginfo: dict = {}, kiegeszites: str = "") -> str:

    kulcsszavak = ", ".join(szakma_info.get("utos_kulcsszavak", []))
    evek = szakma_info.get("tapasztalat_evek", 0)
    if evek and evek > 0:
        evek_utasitas = f"\nA tapasztalat éveinek száma PONTOSAN {evek} év — MINDENHOL ezt használd, ne találj ki más számot."
    else:
        evek_utasitas = "\nNE írj konkrét évszámot a tapasztalatra; fogalmazz általánosan (pl. „több éves tapasztalat”)."
    hianyzok = diagnozis.get("hianyzo_kulcsszavak", [])
    hianyzo_lista = ", ".join([h.get("szo", "") for h in hianyzok if h.get("szo")])

    hianyzo_utasitas = ""
    if hianyzo_lista:
        hianyzo_utasitas = (
            f"\nKÖTELEZŐ TERMÉSZETESEN BEÉPÍTENI (ezek hiányoznak, ezért szűr ki a robot): "
            f"{hianyzo_lista}"
        )

    ceg_kontextus = ""
    if ceginfo:
        ceg_kontextus = f"\nCég profilja: {ceginfo.get('leiras', '')} | Méret: {ceginfo.get('meret', '')}"

    kieg_utasitas = ""
    if kiegeszites and kiegeszites.strip():
        kieg_utasitas = (
            f"\nA JELÖLT EZT SZERETNÉ KIEMELNI (építsd be természetesen, szakmai nyelven, "
            f"a megfelelő szekcióba — pl. nyelvtudás a készségekhez): {kiegeszites.strip()}"
        )

    prompt = f"""Te Magyarország legjobb CV-írója vagy. Magyar anyanyelvű, profi, gördülékeny szövegeket írsz.

ÁLLÁS:
Pozíció: {allas.get('cim', '')}
Cég: {allas.get('ceg', '')}
Elvárások: {allas.get('snippet', '')}{ceg_kontextus}

EREDETI CV:
{cv_szoveg}

Szakmai kulcsszavak: {kulcsszavak}{hianyzo_utasitas}{evek_utasitas}{kieg_utasitas}

Készíts egy profi, magyaros CV-t:

1. ÁTMEGY AZ ATS-EN: a hiányzó kulcsszavak természetesen, mondatba ágyazva jelenjenek meg — ne kulcsszó-felsorolásként.
2. MEGGYŐZI AZ EMBERT: erős, aktív igék (vezette, optimalizálta, kezelte); konkrét számok ahol van; a legerősebb tapasztalat előre.
3. SZAKMAI NYELVEZET: a jelölt pongyola megfogalmazását MINDEN szakmában fordítsd szakmaira. Példák az elvre (bármely szakmára alkalmazd): "árut raktam ki" → "árufeltöltés"; "pénztárazás" → "pénztárgép kezelése"; "vért vettem" → "vérvétel végzése"; "vezetéket kötöttem" → "elektromos hálózat kiépítése".
4. STRUKTÚRA Markdown formátumban, PONTOSAN így, hogy a sablon felismerje:
   - A CV ELEJÉN kötelező egy "## SZAKMAI PROFIL" szekció: 2-3 mondatos, erős összefoglaló a jelöltről, tele a célállás kulcsszavaival (ez az első, amit a recruiter elolvas).
   - Utána: "## SZAKMAI TAPASZTALAT", "## VÉGZETTSÉG", "## KÉSZSÉGEK"
   - Munkahely címe félkövéren: **Pozíció — Cég**
   - Cég/időszak dőlten: *2018–2024*
   - Felsorolás: "- " kötőjellel kezdődő sorok
5. NE írj a CV szövegébe elérhetőséget (név, telefon, email, lakcím) — azt a sablon fejléce adja. A CV egyből a "## SZAKMAI PROFIL" szekcióval kezdődjön.
6. SOHA: ne találj ki tapasztalatot ami nincs a CV-ben; ne legyen 2 oldalnál hosszabb; ne legyen sablonos.

Csak a kész CV szövegét add vissza, Markdown formátumban."""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text.strip()


# ── 6. MOTIVÁCIÓS LEVÉL ──────────────────────────────────────

def motivacios_level(cv_szoveg: str, allas: dict,
                     szakma_info: dict, ceginfo: dict = {}, kiegeszites: str = "") -> str:

    ceg_nev = allas.get('ceg', '')
    pozicio = allas.get('cim', '')
    evek = szakma_info.get("tapasztalat_evek", 0)
    if evek and evek > 0:
        evek_utasitas = f"\nA tapasztalat éveinek száma PONTOSAN {evek} év — ezt használd, ne találj ki más számot."
    else:
        evek_utasitas = "\nNE írj konkrét évszámot a tapasztalatra; fogalmazz általánosan."

    ceg_kontextus = ""
    if ceginfo:
        ceg_kontextus = (
            f"\nCéginfó, amit felhasználhatsz:\n"
            f"- {ceginfo.get('leiras', '')}\n"
            f"- Méret: {ceginfo.get('meret', '')}\n"
            f"Írj a cég szempontjából — mit nyer a cég, ha felveszi ezt a jelöltet."
        )

    kieg_utasitas = ""
    if kiegeszites and kiegeszites.strip():
        kieg_utasitas = f"\nA jelölt ki szeretné emelni (építsd be természetesen): {kiegeszites.strip()}"

    prompt = f"""Te egy 15 éves tapasztalatú magyar HR szakember vagy, aki több ezer motivációs levelet írt.
Magyar anyanyelvű, gördülékeny, természetes szöveget írsz.

ÁLLÁS:
Pozíció: {pozicio}
Cég: {ceg_nev}
Elvárások: {allas.get('snippet', '')}{ceg_kontextus}

A JELÖLT:
{cv_szoveg}
{evek_utasitas}{kieg_utasitas}

Írj egy profi motivációs levelet, pontosan ezzel a felépítéssel:

Megszólítás: "Tisztelt {ceg_nev} Humán Erőforrás Osztálya!" (SOHA ne a platformot szólítsd meg)

1. bekezdés — Miért én + miért ez a pozíció: azonnal a lényeg, konkrét számmal vagy ténnyel az első mondatban. Ne "büszkeséggel jelentkezem".
2. bekezdés — Bizonyíték: konkrét, releváns tapasztalat számokkal, a cég szempontjából megfogalmazva.
3. bekezdés — Motiváció + magabiztos zárás interjú-meghívással. Ne könyörgő.

Hangvétel: professzionális de emberi, magabiztos de nem arrogáns, tömör (max 3 bekezdés).

FONTOS:
- NE írd bele a levélbe a telefonszámot és az email-címet — azok a fejlécben már szerepelnek. A zárásban elég a név.
- SZAKMAI nyelvezet: a jelölt pongyola megfogalmazását MINDEN szakmában fordítsd szakmaira. Példák az elvre (bármely szakmára alkalmazd): "pénztárazás" → "pénztárgép kezelése"; "árut pakoltam" → "árufeltöltés"; "vért vettem" → "vérvétel végzése".

Csak a kész levelet add vissza."""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text.strip()


# ── 7. KÉPZÉS AJÁNLAT (kurált adatbázisból, API nélkül) ──────

def kepzes_ajanlat(szakma: str, hianyok: list = None,
                   szakma_kategoria: str = "") -> list:
    """Kurált képzési adatbázisból válogat a szakmához – NEM keres, NEM hív API-t.
    Így gyors, ingyenes, és a linkek mindig valódiak (nincs hallucináció)."""
    try:
        from agents.kepzes_db import kepzesek_szakmahoz
    except Exception:
        try:
            from kepzes_db import kepzesek_szakmahoz
        except Exception:
            return []

    talalatok = kepzesek_szakmahoz(szakma, szakma_kategoria, max_db=4)

    # A felület 'miert_fontos' kulcsot vár; az adatbázisban 'miert_jo' van → átnevezzük
    eredmeny = []
    for t in talalatok:
        eredmeny.append({
            "nev": t.get("nev", ""),
            "szolgaltato": t.get("szolgaltato", ""),
            "link": t.get("link", ""),
            "idotartam": t.get("idotartam", ""),
            "ar": t.get("ar", ""),
            "miert_fontos": t.get("miert_jo", ""),
        })
    return eredmeny


# ── 8. ÉKEZETMENTESÍTÉS (fájlnevekhez) ───────────────────────

def ekezet_nelkul(szoveg: str) -> str:
    csere = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ö': 'o',
        'ő': 'o', 'ú': 'u', 'ü': 'u', 'ű': 'u',
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ö': 'O',
        'Ő': 'O', 'Ú': 'U', 'Ü': 'U', 'Ű': 'U'
    }
    for eredeti, uj in csere.items():
        szoveg = szoveg.replace(eredeti, uj)
    return re.sub(r'[^a-zA-Z0-9_]', '_', szoveg)


# ── 9. FŐ FÜGGVÉNY ───────────────────────────────────────────

# ── 7/B. ÁLLÁSOK RANGSOROLÁSA (1 modellhívás, top 5) ─────────

def allasok_rangsorolasa(cv_szoveg: str, allasok: list, szakma_info: dict,
                         top_n: int = 5) -> list:
    """A talált hirdetéseket EGYETLEN modellhívással összeveti a CV-vel,
    illeszkedés szerint pontozza, és a legjobb (max top_n) állást adja vissza.
    CV nélkül egyszerűen az első top_n állást adja (nincs mit pontozni)."""
    if not allasok:
        return []
    # CV nélkül nem tudunk illeszkedést mérni -> első néhány, semleges pontszámmal
    if not cv_szoveg:
        return [dict(a, illeszkedes=0, indoklas="") for a in allasok[:top_n]]

    # Az összes hirdetést EGYBEN adjuk a modellnek -> 1 hívás
    lista_szoveg = "\n\n".join([
        f"[{i}] Cég: {a.get('ceg','')} | Pozíció: {a.get('cim','')}\n"
        f"Elvárások: {a.get('snippet','')}"
        for i, a in enumerate(allasok)
    ])

    prompt = f"""Te egy magyar recruiter vagy. Egy jelölt CV-jét kell összevetned több álláshirdetéssel.

JELÖLT CV-je:
{cv_szoveg}

Szakma: {szakma_info.get('szakma','')}

ÁLLÁSHIRDETÉSEK (sorszámmal):
{lista_szoveg}

Feladat: pontozd MINDEGYIK hirdetést 0–100 között aszerint, mennyire illik a jelölthöz
(tapasztalat, készségek, szakma egyezése alapján), és rangsorold a legjobbtól.

Válaszolj KIZÁRÓLAG JSON-tömbként, a legjobbtól a leggyengébbig rendezve:
[
  {{"index": 0, "illeszkedes": 85, "indoklas": "Rövid, konkrét indok (1 mondat)"}}
]
Csak a hirdetések sorszámait (index) használd, semmi mást ne adj hozzá."""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=800,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        szoveg = response.content[0].text.strip()
        if "```json" in szoveg:
            szoveg = szoveg.split("```json")[1].split("```")[0].strip()
        elif "```" in szoveg:
            szoveg = szoveg.split("```")[1].split("```")[0].strip()
        rangsor = json.loads(szoveg)
    except Exception:
        # Ha a rangsorolás bármiért elhasal, ne dőljön össze: első top_n állás
        return [dict(a, illeszkedes=0, indoklas="") for a in allasok[:top_n]]

    eredmeny = []
    for elem in rangsor:
        idx = elem.get("index")
        if isinstance(idx, int) and 0 <= idx < len(allasok):
            allas = dict(allasok[idx])
            allas["illeszkedes"] = elem.get("illeszkedes", 0)
            allas["indoklas"] = elem.get("indoklas", "")
            eredmeny.append(allas)
        if len(eredmeny) >= top_n:
            break

    # Ha a modell kevesebbet adott vissza, töltsük fel a maradékból
    if not eredmeny:
        eredmeny = [dict(a, illeszkedes=0, indoklas="") for a in allasok[:top_n]]
    return eredmeny


def keszsegek_kinyerese(allasok: list) -> list:
    """EGY Haiku-hívással kinyeri MINDEN hirdetésből a készségeket
    (elvárás / feladat / eszköz / soft) — az adatbázisba mentéshez.
    Visszatérés: listák listája, az allasok sorrendjében."""
    if not allasok:
        return []

    lista = "\n\n".join([
        f"[{i}] {a.get('cim','')} — {a.get('ceg','')}\n{a.get('snippet','')}"
        for i, a in enumerate(allasok)
    ])

    prompt = f"""Álláshirdetésekből kell strukturáltan kinyerned a készségeket és elvárásokat.

HIRDETÉSEK (sorszámmal):
{lista}

Minden hirdetéshez add meg a benne szereplő készségeket SZAKMAI néven:
- tipus lehet: "elvaras" (elvárt tudás/tapasztalat/végzettség), "feladat" (a munkakörben végzendő tevékenység), "eszkoz" (szoftver, gép, technológia), "soft" (személyes készség, pl. csapatmunka)
- A pongyola megfogalmazást fordítsd szakmaira (pl. "kassza" → "pénztárgép kezelése").
- A nevet kisbetűvel írd, KIVÉVE a rövidítéseket és tulajdonneveket (HACCP, SQL, Python).
- Hirdetésenként 3-8 elem. Helyszínt, bért, munkaidőt, juttatást NE adj meg készségként.

Válaszolj KIZÁRÓLAG JSON-tömbként:
[
  {{"index": 0, "keszsegek": [{{"nev": "pénztárgép kezelése", "tipus": "feladat"}}]}}
]"""

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5", max_tokens=2000, temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        t = resp.content[0].text.strip()
        if "```json" in t:
            t = t.split("```json")[1].split("```")[0].strip()
        elif "```" in t:
            t = t.split("```")[1].split("```")[0].strip()
        adat = json.loads(t)
        eredmeny = [[] for _ in allasok]
        for elem in adat:
            idx = elem.get("index")
            if isinstance(idx, int) and 0 <= idx < len(allasok):
                eredmeny[idx] = elem.get("keszsegek", [])
        return eredmeny
    except Exception as e:
        print(f"[adatbazis] Keszseg-kinyeres hiba: {e}")
        return [[] for _ in allasok]


def run(cv_szoveg: str = "", szakma_megadva: str = "",
        helyszin: str = "Budapest") -> dict:

    print("Karrier Ugynok indul...")

    szakma_info = szakma_felismeres(cv_szoveg, szakma_megadva)
    szakma = szakma_info.get("szakma", szakma_megadva or "altalanos")
    print(f"Szakma: {szakma}")

    nyers_allasok = allasok_keresese(szakma, helyszin, szakma_info.get("ajanlott_cegek", []))
    if not nyers_allasok:
        return {"hiba": "Nem találtunk állásokat!", "szakma_info": szakma_info}

    # A találatokat illeszkedés szerint rangsoroljuk -> legjobb max 5 (1 modellhívás)
    top_allasok = allasok_rangsorolasa(cv_szoveg, nyers_allasok, szakma_info, top_n=5)

    # ── PASSZÍV ADATGYŰJTÉS: az ÖSSZES talált hirdetést mentjük Supabase-be ──
    # (nem csak a top 5-öt — minden adat érték!) Hibatűrő: ha nincs Supabase
    # beállítva vagy bármi hiba van, az alkalmazás zavartalanul megy tovább.
    if not TESZT_MOD:
        try:
            keszsegek = keszsegek_kinyerese(nyers_allasok)
            gyujtes_mentese(szakma_info, nyers_allasok, keszsegek)
        except Exception as e:
            print(f"[adatbazis] Gyujtes kihagyva: {e}")

    # CÉGINFÓT NEM hívunk itt — csak a felületi gomb kéri le (kredit-kímélés)

    # Diagnózis a top állások elvárásai alapján (1 hívás, a legjobb találatokra)
    diagnozis = {}
    if cv_szoveg:
        diagnozis = ats_diagnozis(cv_szoveg, top_allasok, szakma_info)
        print(f"Illeszkedes: {diagnozis.get('illeszkedes_szazalek', 0)}%")

    # Képzés-ajánlat MINDIG elérhető (kurált adatbázisból, ingyenes) –
    # a felületen gombra jelenik meg, nem tolakodó.
    kepzesek = kepzes_ajanlat(
        szakma,
        diagnozis.get("hianyzo_kulcsszavak", []),
        szakma_info.get("szakma_kategoria", "")
    )

    print(f"Karrier Ugynok kesz! ({len(top_allasok)} allas)")

    csomagok = [{
        "cim": a.get("cim", ""),
        "ceg": a.get("ceg", ""),
        "link": a.get("link", ""),
        "illeszkedes": a.get("illeszkedes", 0),
        "indoklas": a.get("indoklas", ""),
        "cv": "",
        "motivacios_level": "",
        "jovahagyva": False
    } for a in top_allasok]

    return {
        "szakma_info": szakma_info,
        "allasok": top_allasok,
        "diagnozis": diagnozis,
        "csomagok": csomagok,
        "kepzesek": kepzesek,
        "portfilio_ajanlott": szakma_info.get("portfilio_ajanlott", False)
    }