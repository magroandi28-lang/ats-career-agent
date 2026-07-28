# -*- coding: utf-8 -*-
"""ESCO-betöltő: a mérce beemelése az adatbázisba.

Az ESCO hivatalos, magyar nyelvű foglalkozás- és készség-osztályozás.
Ez adja meg, MI TARTOZIK egy szakmához -- szemben a hirdetésekkel, amik
azt mondják meg, mit kér belőle a magyar piac most.

A csomag letöltése: https://esco.ec.europa.eu/hu/use-esco/download
    Változat: ESCO adatkészlet v1.2.x | Tartalom: Osztályozás
    Fájltípus: csv | Nyelv: hu

Futtatás a projekt gyökeréből:
    python scripts/esco_betolto.py "C:/.../ESCO dataset - ... - hu - csv.zip"

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


def main() -> int:
    if len(sys.argv) < 2:
        print("Add meg az ESCO ZIP útvonalát.")
        return 1
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
