# -*- coding: utf-8 -*-
"""ESCO-betöltő: a mérce beemelése az adatbázisba.

Az ESCO hivatalos, magyar nyelvű foglalkozás- és készség-osztályozás.
Ez adja meg, MI TARTOZIK egy szakmához -- szemben a hirdetésekkel, amik
azt mondják meg, mit kér belőle a magyar piac most.

A csomag letöltése: https://esco.ec.europa.eu/hu/use-esco/download
    Változat: ESCO adatkészlet v1.2.x | Tartalom: Osztályozás
    Fájltípus: csv | Nyelv: hu

Futtatás a projekt gyökeréből:
    python scripts/esco_betolto.py "…hu - csv.zip"
    python scripts/esco_betolto.py --angol "…en - csv.zip"

Az `--angol` csak a foglalkozások angol neveit tölti be a magyar sorokra:
sok multi angolul hirdet, és a besoroló szótára enélkül nem ismeri fel őket.
Az URI-k mindkét csomagban azonosak, a készségkapcsolatok pedig
nyelvfüggetlenek -- azokat nem kell újratölteni.

Újrafuttatható: mindent felülír (upsert), semmit nem duplikál.
Nulla modellhívás.
"""

import csv
import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.adatbazis import kliens  # noqa: E402


ADAG = 1000


def _csv(z: zipfile.ZipFile, nev: str) -> list[dict]:
    with z.open(nev) as f:
        return list(csv.DictReader(io.TextIOWrapper(f, "utf-8")))


def _cimkek(szoveg: str) -> list[str]:
    """Az ESCO soronként sorolja fel az alternatív neveket."""
    return [s.strip() for s in (szoveg or "").split("\n") if s.strip()]


def _feltolt(db, tabla: str, sorok: list[dict], kulcs: str) -> int:
    """Adagolt upsert -- 126 ezer sor egyben nem megy át a REST-en."""
    for i in range(0, len(sorok), ADAG):
        adag = sorok[i:i + ADAG]
        db.table(tabla).upsert(adag, on_conflict=kulcs).execute()
        print(f"    {tabla}: {min(i + ADAG, len(sorok))}/{len(sorok)}", end="\r")
    print(f"    {tabla}: {len(sorok)}/{len(sorok)}      ")
    return len(sorok)


def angol_nevek(ut: Path, db) -> int:
    """Csak az angol foglalkozásneveket írja rá a meglévő sorokra."""
    z = zipfile.ZipFile(ut)
    nev = next(n for n in (i.filename for i in z.infolist())
               if n.startswith("occupations_") and n.endswith(".csv"))
    sorok = {}
    for r in _csv(z, nev):
        if r.get("preferredLabel"):
            sorok[r["conceptUri"]] = {
                "uri": r["conceptUri"],
                "nev_en": r["preferredLabel"],
                "alt_nevek_en": _cimkek(r.get("altLabels")),
            }
    # Kötegelt upsert, nem soronkénti update: az utóbbi 3 039 külön hívás
    # lenne. Az upserthez viszont kell a magyar `nev` is (NOT NULL), ezért
    # előbb beolvassuk a meglévő sorokat.
    meglevo, kezdet = {}, 0
    while True:
        adag = (db.table("esco_foglalkozas").select("uri, nev")
                .range(kezdet, kezdet + 999).execute().data or [])
        meglevo.update({r["uri"]: r["nev"] for r in adag})
        if len(adag) < 1000:
            break
        kezdet += 1000

    lista = [{"uri": u, "nev": meglevo[u],
              "nev_en": s["nev_en"], "alt_nevek_en": s["alt_nevek_en"]}
             for u, s in sorok.items() if u in meglevo]
    hianyzo = len(sorok) - len(lista)
    print(f"Angol nevek: {len(lista)} foglalkozásra"
          + (f" ({hianyzo} URI nincs a magyar csomagban)" if hianyzo else ""))

    for i in range(0, len(lista), ADAG):
        db.table("esco_foglalkozas").upsert(
            lista[i:i + ADAG], on_conflict="uri").execute()
        print(f"    {min(i + ADAG, len(lista))}/{len(lista)}", end="\r")
    print(f"    {len(lista)}/{len(lista)}      ")
    return len(lista)


def angol_nevek_apibol(db) -> int:
    """Angol nevek az ESCO nyilvános API-jából, URI-nként.

    Alternatíva a ZIP-hez: a letöltő oldal CAPTCHA mögött van, az API nem.
    Lassabb (foglalkozásonként egy kérés), de egyszeri, és nem kell hozzá
    semmit letölteni. Adagonként ment, tehát egy megszakadt futás sem vész el.
    """
    import time
    import requests

    fejlec = {"User-Agent": "karrier-ugynokseg/1.0", "Accept": "application/json"}
    vegpont = "https://ec.europa.eu/esco/api/resource/occupation"

    sorok, kezdet = [], 0
    while True:
        adag = (db.table("esco_foglalkozas").select("uri, nev")
                .is_("nev_en", "null").range(kezdet, kezdet + 999).execute().data or [])
        sorok += adag
        if len(adag) < 1000:
            break
        kezdet += 1000

    print(f"Angol név nélküli foglalkozás: {len(sorok)}")
    kesz, hiba, puffer = 0, 0, []
    for i, sor in enumerate(sorok, start=1):
        try:
            r = requests.get(vegpont, params={"uri": sor["uri"], "language": "en"},
                             headers=fejlec, timeout=20)
            d = r.json() if "json" in (r.headers.get("content-type") or "") else None
        except Exception:
            d = None
        if d and d.get("title"):
            puffer.append({
                "uri": sor["uri"],
                "nev": sor["nev"],
                "nev_en": d["title"],
                "alt_nevek_en": list((d.get("alternativeLabel") or {}).get("en", []))[:30],
            })
            kesz += 1
        else:
            hiba += 1
        if len(puffer) >= 200:
            db.table("esco_foglalkozas").upsert(puffer, on_conflict="uri").execute()
            puffer = []
        if i % 100 == 0:
            print(f"    {i}/{len(sorok)}  (siker {kesz}, hiba {hiba})", end="\r")
        # Nyilvános EU-kiszolgáló: ne terheljük.
        time.sleep(0.15)

    if puffer:
        db.table("esco_foglalkozas").upsert(puffer, on_conflict="uri").execute()
    print(f"    {len(sorok)}/{len(sorok)}  (siker {kesz}, hiba {hiba})      ")
    return kesz


def main() -> int:
    if len(sys.argv) < 2:
        print("Add meg az ESCO ZIP útvonalát.")
        return 1

    if sys.argv[1] == "--angol-api":
        db = kliens()
        if db is None:
            print("Nincs adatbázis-kapcsolat.")
            return 1
        angol_nevek_apibol(db)
        print("Kész. Frissítsd a névlistát:")
        print("    refresh materialized view public.esco_nev;")
        return 0

    if sys.argv[1] == "--angol":
        if len(sys.argv) < 3:
            print("Add meg az ANGOL ESCO ZIP útvonalát.")
            return 1
        db = kliens()
        if db is None:
            print("Nincs adatbázis-kapcsolat.")
            return 1
        angol_nevek(Path(sys.argv[2]), db)
        print("Kész. Frissítsd a névlistát:")
        print("    refresh materialized view public.esco_nev;")
        return 0

    ut = Path(sys.argv[1])
    if not ut.exists():
        print(f"Nincs ilyen fájl: {ut}")
        return 1

    db = kliens()
    if db is None:
        print("Nincs adatbázis-kapcsolat.")
        return 1

    z = zipfile.ZipFile(ut)
    nevek = {i.filename for i in z.infolist()}

    def fajl(alap: str) -> str:
        for n in nevek:
            if n.startswith(alap) and n.endswith(".csv"):
                return n
        raise SystemExit(f"Hiányzik a csomagból: {alap}*.csv")

    print("Olvasás...")
    foglalkozasok = _csv(z, fajl("occupations_"))
    keszsegek = _csv(z, fajl("skills_"))
    kapcsolatok = _csv(z, fajl("occupationSkillRelations_"))
    print(f"  {len(foglalkozasok)} foglalkozás, {len(keszsegek)} készség, "
          f"{len(kapcsolatok)} kapcsolat")

    # A `normalizalt` oszlop generált -- nem szabad beküldeni.
    f_sorok = [{
        "uri": r["conceptUri"],
        "isco_kod": (r.get("code") or "").strip() or None,
        "isco_csoport": (r.get("iscoGroup") or "").strip() or None,
        "nev": r["preferredLabel"],
        "alt_nevek": _cimkek(r.get("altLabels")),
        "leiras": (r.get("description") or "").strip() or None,
    } for r in foglalkozasok if r.get("preferredLabel")]

    k_sorok = [{
        "uri": r["conceptUri"],
        "nev": r["preferredLabel"],
        "tipus": (r.get("skillType") or "").strip() or None,
        "ujrahasznosithatosag": (r.get("reuseLevel") or "").strip() or None,
        "leiras": (r.get("description") or "").strip() or None,
    } for r in keszsegek if r.get("preferredLabel")]

    # Ugyanaz az URI többször is szerepel a CSV-ben (nyelvi változatok miatt).
    # Egy upsert-adagon belül ez hibát ad, ezért URI-ra egyedivé tesszük.
    def egyedi(sorok: list[dict]) -> list[dict]:
        latott: dict[str, dict] = {}
        for r in sorok:
            latott.setdefault(r["uri"], r)
        return list(latott.values())

    elotte_f, elotte_k = len(f_sorok), len(k_sorok)
    f_sorok, k_sorok = egyedi(f_sorok), egyedi(k_sorok)
    if elotte_f != len(f_sorok) or elotte_k != len(k_sorok):
        print(f"  duplikátum kiszűrve: foglalkozás {elotte_f - len(f_sorok)}, "
              f"készség {elotte_k - len(k_sorok)}")

    f_uri = {r["uri"] for r in f_sorok}
    k_uri = {r["uri"] for r in k_sorok}

    # Az idegen kulcs miatt csak olyan kapcsolat mehet be, aminek mindkét
    # vége létezik. Egy hiányzó URI különben az egész adagot megbuktatná.
    parok: dict[tuple[str, str], bool] = {}
    kihagyott = 0
    for r in kapcsolatok:
        fo, ke = r.get("occupationUri"), r.get("skillUri")
        if fo not in f_uri or ke not in k_uri:
            kihagyott += 1
            continue
        kotelezo = (r.get("relationType") or "").strip() == "essential"
        # Ha ugyanaz a pár többször szerepel, a kötelező az erősebb.
        parok[(fo, ke)] = parok.get((fo, ke), False) or kotelezo

    kap_sorok = [{"foglalkozas_uri": f, "keszseg_uri": k, "kotelezo": v}
                 for (f, k), v in parok.items()]

    print("Feltöltés...")
    _feltolt(db, "esco_foglalkozas", f_sorok, "uri")
    _feltolt(db, "esco_keszseg", k_sorok, "uri")
    _feltolt(db, "esco_foglalkozas_keszseg", kap_sorok,
             "foglalkozas_uri,keszseg_uri")

    print()
    print(f"Kész. Kihagyott kapcsolat (ismeretlen URI): {kihagyott}")
    print("A szakma-hozzárendelés külön lépés: scripts/esco_szakma_parositas.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
