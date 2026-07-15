# -*- coding: utf-8 -*-
# Kurált képzési adatbázis - agents/kepzes_db.py
# Valós, ellenőrzött, piacképes képzések. A modell NEM keres, ebből választ.
# Bővíthető: új területet vagy képzést egyszerűen hozzáadsz a megfelelő listához.

KEPZES_DB = {
    # ── IT / FEJLESZTŐ / MESTERSÉGES INTELLIGENCIA ──────────────
    "it": [
        {
            "nev": "Mesterséges Intelligencia – ingyenes magyar MI/Python kurzus",
            "szolgaltato": "mesterin.hu (Baráth András)",
            "link": "https://mesterin.hu/",
            "idotartam": "3 nap, napi ~10 perc (alapozó)",
            "ar": "Ingyenes",
            "miert_jo": "Magyar nyelvű, gyakorlatias bevezető a Python + gépi tanulás világába, valós üzleti példákkal."
        },
        {
            "nev": "Microsoft Azure AI Fundamentals (AI-900 / AI-901)",
            "szolgaltato": "Microsoft Learn (hivatalos)",
            "link": "https://learn.microsoft.com/hu-hu/credentials/certifications/azure-ai-fundamentals/",
            "idotartam": "kb. 10–20 óra önálló tanulás",
            "ar": "Tananyag ingyenes; vizsga kb. 165 USD",
            "miert_jo": "Nemzetközileg elismert AI-alapozó certifikáció. (Az AI-900 2026 közepétől AI-901-re vált.)"
        },
        {
            "nev": "Microsoft Azure Fundamentals (AZ-900)",
            "szolgaltato": "Microsoft Learn (hivatalos)",
            "link": "https://learn.microsoft.com/hu-hu/credentials/certifications/azure-fundamentals/",
            "idotartam": "kb. 10–15 óra",
            "ar": "Tananyag ingyenes; vizsga kb. 165 USD",
            "miert_jo": "A felhő alapjai – szinte minden IT állásban előny, belépő a teljes Azure certifikációs útvonalhoz."
        },
        {
            "nev": "Python tanfolyam (kezdő → haladó)",
            "szolgaltato": "Ruander",
            "link": "https://www.ruander.hu/python-tanfolyam.html",
            "idotartam": "tanfolyam-függő",
            "ar": "Fizetős (tanfolyam-függő)",
            "miert_jo": "Strukturált, magyar nyelvű, gyakorlatorientált Python képzés kezdőtől."
        },
        {
            "nev": "AI, szoftver és karrierépítő képzések (élő, online)",
            "szolgaltato": "Gerilla Mentor Klub",
            "link": "https://gerillamentorklub.hu/",
            "idotartam": "4–12 hetes élő képzések, munka mellett is",
            "ar": "Előfizetés kb. 19.950 Ft/hó-tól; szakképesítő vizsga külön (kb. 40–70e Ft)",
            "miert_jo": "Magyar nyelvű, gyakorlatorientált képzések (AI, szoftver, nyelv) és álláskeresési modul; középfokú végzettséggel is elérhető."
        },
    ],

    # ── ADAT / DATA ─────────────────────────────────────────────
    "data": [
        {
            "nev": "Microsoft Azure Data Fundamentals (DP-900)",
            "szolgaltato": "Microsoft Learn (hivatalos)",
            "link": "https://learn.microsoft.com/hu-hu/credentials/certifications/azure-data-fundamentals/",
            "idotartam": "kb. 10–15 óra",
            "ar": "Tananyag ingyenes; vizsga kb. 165 USD",
            "miert_jo": "Adatkezelési alapok a felhőben – data-elemző és -mérnök szerepek belépője."
        },
        {
            "nev": "Google Data Analytics Professional Certificate",
            "szolgaltato": "Coursera (Google)",
            "link": "https://www.coursera.org/professional-certificates/google-data-analytics",
            "idotartam": "kb. 6 hónap, heti pár óra",
            "ar": "Coursera-előfizetés (gyakran van pénzügyi támogatás)",
            "miert_jo": "Nemzetközileg ismert, kezdőbarát adatelemző certifikáció – portfólióprojektekkel."
        },
    ],

    # ── KERESKEDELEM / ELADÓ / ÜGYFÉLSZOLGÁLAT ──────────────────
    "kereskedelem": [
        {
            "nev": "Eladó / kereskedelmi felnőttképzések",
            "szolgaltato": "Akkreditált felnőttképző intézmények",
            "link": "https://felnottkepzes.munka.hu/",
            "idotartam": "képzés-függő",
            "ar": "Gyakran államilag támogatott / ingyenes",
            "miert_jo": "Hivatalos, elismert szakmai bizonyítvány – sok álláshirdetésben elvárás."
        },
        {
            "nev": "Ügyfélszolgálati és kommunikációs készségfejlesztés",
            "szolgaltato": "Online platformok (pl. Coursera, Udemy)",
            "link": "https://www.coursera.org/courses?query=customer%20service",
            "idotartam": "néhány óra – pár hét",
            "ar": "Ingyenes / olcsó kurzusok is",
            "miert_jo": "A vevőkiszolgálás és panaszkezelés bizonyíthatóan erősíti a jelentkezést a kereskedelemben."
        },
    ],

    # ── NYELVI (minden szakmában előny) ─────────────────────────
    "nyelvi": [
        {
            "nev": "Angol nyelvtanulás (alap → középfok)",
            "szolgaltato": "Duolingo / British Council",
            "link": "https://www.duolingo.com/",
            "idotartam": "folyamatos, napi pár perc",
            "ar": "Ingyenes (alap)",
            "miert_jo": "Az alap-középfokú angol szinte minden szakmában plusz pont, sok állásban elvárás."
        },
    ],

    # ── ÁLTALÁNOS / DIGITÁLIS ALAPOK (ha nincs jobb találat) ────
    "altalanos": [
        {
            "nev": "Digitális alapkészségek és AI az irodában (Microsoft 365 Copilot)",
            "szolgaltato": "Microsoft Learn (hivatalos)",
            "link": "https://learn.microsoft.com/hu-hu/training/",
            "idotartam": "önálló tempó",
            "ar": "Ingyenes",
            "miert_jo": "Digitális és AI-eszközök használata – ma már szinte minden munkakörben elvárás."
        },
        {
            "nev": "freeCodeCamp – ingyenes fejlesztői képzések",
            "szolgaltato": "freeCodeCamp",
            "link": "https://www.freecodecamp.org/",
            "idotartam": "önálló tempó",
            "ar": "Ingyenes",
            "miert_jo": "Teljesen ingyenes, projektalapú tanulás, nemzetközileg ismert."
        },
        {
            "nev": "Karrierváltó és álláskeresési képzések (pályaorientáció, interjú, bértárgyalás)",
            "szolgaltato": "Gerilla Mentor Klub",
            "link": "https://gerillamentorklub.hu/",
            "idotartam": "élő online tréningek, rugalmas",
            "ar": "Előfizetés kb. 19.950 Ft/hó-tól",
            "miert_jo": "Karrierváltóknak: pályaorientáció, önéletrajz/LinkedIn, interjú- és bértárgyalás-felkészítés, középfokú végzettséggel is."
        },
    ],
}

# Szakma-kategória → adatbázis-terület megfeleltetés (kulcsszó alapú)
_TERULET_KULCSOK = {
    "it": ["it", "informatik", "fejleszt", "programoz", "szoftver", "python",
           "developer", "mérnök", "ai", "mesterséges", "gépi tanulás", "data scientist"],
    "data": ["adat", "data", "elemző", "analyst", "bi", "adatbázis"],
    "kereskedelem": ["keresked", "eladó", "pénztáros", "bolti", "értékesít",
                     "ügyfél", "vevő", "shop", "retail"],
}


def kepzesek_szakmahoz(szakma: str, szakma_kategoria: str = "", max_db: int = 4) -> list:
    """Kurált adatbázisból válogat a szakmához – API-hívás NÉLKÜL.
    Mindig ad eredményt: ha nincs pontos terület, általános + nyelvi képzéseket ad."""
    szoveg = f"{szakma} {szakma_kategoria}".lower()

    talalt_terulet = None
    for terulet, kulcsok in _TERULET_KULCSOK.items():
        if any(k in szoveg for k in kulcsok):
            talalt_terulet = terulet
            break

    eredmeny = []
    if talalt_terulet:
        eredmeny.extend(KEPZES_DB.get(talalt_terulet, []))

    # Nyelvi mindig hasznos, ha van még hely
    eredmeny.extend(KEPZES_DB.get("nyelvi", []))

    # Ha kevés a találat, általánossal töltjük fel
    if len(eredmeny) < max_db:
        eredmeny.extend(KEPZES_DB.get("altalanos", []))

    # Duplikátumok kiszűrése név alapján, és vágás max_db-re
    latott, vegleges = set(), []
    for k in eredmeny:
        if k["nev"] not in latott:
            latott.add(k["nev"])
            vegleges.append(k)
        if len(vegleges) >= max_db:
            break
    return vegleges