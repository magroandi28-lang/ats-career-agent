# -*- coding: utf-8 -*-
"""A repo migrációs fájljai és az éles adatbázis naplója közti eltérés.

MIÉRT KELL: 2026-07-28-án kiderült, hogy a kettő elcsúszott -- a DB naplója
7 bejegyzést ismert, a repóban 9 fájl volt, a metszet 4. Az ok, hogy DDL ment
be kézzel, SQL-szerkesztőből. Következmény: az adatbázis NEM ÉPÍTHETŐ ÚJRA a
repóból, és egy második környezet más sémát kapna.

A szkript összeveti a kettőt, és `--ir` kapcsolóval pótolja a hiányzó
fájlokat az adatbázis naplójából.

FIGYELEM: ez utólagos javítás, nem megoldás. A megelőzés az, hogy DDL CSAK
migrációval megy be. Ezt a szkriptet CI-ben is érdemes futtatni: ha eltérést
talál, a build bukjon el.

Futtatás a projekt gyökeréből:
    python scripts/migracio_szinkron.py         # csak jelentés
    python scripts/migracio_szinkron.py --ir    # hiányzó fájlok pótlása
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.adatbazis import kliens  # noqa: E402


MAPPA = Path(__file__).resolve().parent.parent / "supabase" / "migrations"


def main(ir: bool) -> int:
    db = kliens()
    if db is None:
        print("Nincs adatbázis-kapcsolat.")
        return 1

    try:
        elesek = db.rpc("migraciok").execute().data or []
    except Exception as e:
        print(f"Nem sikerült kiolvasni a migrációs naplót: {e}")
        return 1

    fajlok = {}
    for p in sorted(MAPPA.glob("*.sql")):
        m = re.match(r"^(\d{14})_(.+)\.sql$", p.name)
        if m:
            fajlok[m.group(1)] = p

    eles_verziok = {m["version"] for m in elesek}
    csak_repo = sorted(set(fajlok) - eles_verziok)
    csak_db = [m for m in elesek if m["version"] not in fajlok]

    print(f"Éles napló: {len(elesek)} migráció")
    print(f"Repo:       {len(fajlok)} fájl")
    print()

    if csak_db:
        print(f"CSAK AZ ADATBÁZISBAN ({len(csak_db)}) -- a repo nem tudja újraépíteni:")
        for m in csak_db:
            print(f"  {m['version']}  {m['name']}")
    if csak_repo:
        print(f"CSAK A REPÓBAN ({len(csak_repo)}) -- lehet, hogy sosem futott le élesen:")
        for v in csak_repo:
            print(f"  {v}  {fajlok[v].name}")
    if not csak_db and not csak_repo:
        print("Nincs eltérés: a repo és az adatbázis egyezik.")
        return 0

    if not ir:
        print()
        print("Pótlás: python scripts/migracio_szinkron.py --ir")
        # Eltérés esetén hibakóddal lépünk ki, hogy CI-ben megfogható legyen.
        return 1

    for m in csak_db:
        ut = MAPPA / f"{m['version']}_{m['name']}.sql"
        fejlec = (
            f"-- Utólag mentve az éles migrációs naplóból "
            f"({m['version']}).\n"
            f"-- A migráció lefutott az adatbázison, de fájl nem tartozott "
            f"hozzá.\n\n"
        )
        ut.write_text(fejlec + (m["sql"] or "") + "\n", encoding="utf-8")
        print(f"  írva: {ut.name}")
    print(f"\nPótolva: {len(csak_db)} fájl.")
    return 0


if __name__ == "__main__":
    sys.exit(main("--ir" in sys.argv))
