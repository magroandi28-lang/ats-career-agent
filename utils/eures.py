# -*- coding: utf-8 -*-
"""EURES KAPCSOLAT — élő, valódi álláshirdetések az EU hivatalos állásportáljáról.

A https://europa.eu/eures portál publikus keresőmotor-végpontját hívja
(nem hivatalos API, de kulcs nélkül elérhető, ugyanezt hívja a portál is).
Nincs AI-hívás, nincs kvótaköltség — tiszta, valódi adat.

Lefedettség: EU-tagállamok + Izland, Liechtenstein, Norvégia, Svájc.
Az Egyesült Királyság NEM szerepel (Brexit óta kimaradt az EURES hálózatból).
"""

import re
from datetime import datetime, timezone

import requests

_URL = "https://europa.eu/eures/api/jv-searchengine/public/jv-search/search"

# Az EURES teljes lefedettsége (élőben ellenőrizve a referencia-végponton) —
# Magyarország szándékosan kimaradt, mert ez a KÜLFÖLDI fül.
ORSZAGOK = {
    "de": "Németország",
    "at": "Ausztria",
    "nl": "Hollandia",
    "ie": "Írország",
    "be": "Belgium",
    "fr": "Franciaország",
    "es": "Spanyolország",
    "it": "Olaszország",
    "se": "Svédország",
    "dk": "Dánia",
    "fi": "Finnország",
    "no": "Norvégia",
    "ch": "Svájc",
    "pl": "Lengyelország",
    "cz": "Csehország",
    "sk": "Szlovákia",
    "ro": "Románia",
    "hr": "Horvátország",
    "si": "Szlovénia",
    "pt": "Portugália",
    "gr": "Görögország",  # EURES-kód: EL — a keresésnél azt küldjük
    "bg": "Bulgária",
    "ee": "Észtország",
    "lv": "Lettország",
    "lt": "Litvánia",
    "lu": "Luxemburg",
    "mt": "Málta",
    "cy": "Ciprus",
    "is": "Izland",
    "li": "Liechtenstein",
}

# Alapértelmezett (leggyakoribb célországok) — a többi a legördülőből bővíthető.
ALAP_ORSZAGOK = ["de", "at"]

# Az EURES néhány országnál nem a szokásos ISO-kódot várja.
_EURES_KOD = {"gr": "el"}


def _eures_kod(kod: str) -> str:
    return _EURES_KOD.get(kod, kod)


# Megjelenítéshez: EURES-oldali kód -> magyar név (a válaszban pl. "EL" jön vissza).
_MEGJELENIT = {_eures_kod(k): v for k, v in ORSZAGOK.items()}


def _link(azon: str) -> str:
    return f"https://europa.eu/eures/portal/jv-se/jv-details/{azon}?lang=hu"


def _datum(ms) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y.%m.%d.")
    except (TypeError, ValueError):
        return ""


def eures_kereses(kulcsszo: str, orszag_kodok: list, darab: int = 15) -> dict:
    """Élő EURES-keresés kulcsszóra és ország(ok)ra.

    Visszaad: {"ok": bool, "talalatok": int, "allasok": [...], "hiba": str|None}
    Hiba esetén sosem dob kivételt — a hívó fél mindig kap egy használható,
    őszinte választ (nincs kitalált adat, nincs összeomlás).
    """
    if not kulcsszo or not kulcsszo.strip():
        return {"ok": False, "hiba": "Adj meg egy kulcsszót a kereséshez.",
                 "talalatok": 0, "allasok": []}

    try:
        r = requests.post(_URL, json={
            "resultsPerPage": darab,
            "page": 1,
            "sortSearch": "MOST_RECENT",
            "keywords": [{"keyword": kulcsszo.strip(), "specificSearchCode": "EVERYWHERE"}],
            "publicationPeriod": None,
            "occupationUris": [],
            "skillUris": [],
            "requiredExperienceCodes": [],
            "positionScheduleCodes": [],
            "sectorCodes": [],
            "educationAndQualificationLevelCodes": [],
            "positionOfferingCodes": [],
            "locationCodes": [_eures_kod(k) for k in (orszag_kodok or ALAP_ORSZAGOK)],
            "euresFlagCodes": [],
            "otherBenefitsCodes": [],
            "requiredLanguages": [],
            "minNumberPost": None,
            "sessionId": "karrier-ugynokseg",
            "userPreferredLanguage": None,
            "requestLanguage": "hu",
        }, timeout=12)
        r.raise_for_status()
        d = r.json()
    except requests.exceptions.RequestException:
        return {"ok": False,
                 "hiba": "Az EURES állásportál jelenleg nem érhető el. Próbáld újra kicsit később.",
                 "talalatok": 0, "allasok": []}
    except ValueError:
        return {"ok": False, "hiba": "Az EURES váratlan választ adott. Próbáld újra.",
                 "talalatok": 0, "allasok": []}

    allasok = []
    for jv in d.get("jvs", []):
        munkaado = (jv.get("employer") or {}).get("name") or "Ismeretlen munkáltató"
        orszag_lista = list((jv.get("locationMap") or {}).keys())
        leiras_nyers = re.sub(r"<[^>]+>", " ", jv.get("description") or "")
        leiras_nyers = re.sub(r"\s+", " ", leiras_nyers).strip()
        allasok.append({
            "cim": jv.get("title") or "",
            "leiras": (leiras_nyers[:280] + "…") if len(leiras_nyers) > 280 else leiras_nyers,
            "munkaado": munkaado,
            "orszag": ", ".join(_MEGJELENIT.get(o.lower(), o.upper()) for o in orszag_lista) or "—",
            "nyelvek": ", ".join(jv.get("availableLanguages") or []).upper() or "—",
            "foglalkoztatas": ", ".join(jv.get("positionScheduleCodes") or []) or "—",
            "datum": _datum(jv.get("creationDate")),
            "link": _link(jv.get("id", "")),
        })

    return {"ok": True, "talalatok": d.get("numberRecords", len(allasok)),
             "allasok": allasok, "hiba": None}
