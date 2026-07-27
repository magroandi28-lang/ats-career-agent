"""Megméri, letölthető-e a hirdetések teljes szövege az eredeti oldalról.

CSAK OLVAS. Semmit nem ír az adatbázisba, semmit nem módosít -- a
készségkapcsolatok érintetlenek maradnak.

Amit megválaszol:
  - a linkek hány százaléka tölthető le egyáltalán,
  - mennyivel hosszabb a teljes szöveg a mostani ~250 karakternél,
  - mely portálok engedik, melyek tiltják.

Futtatás a projekt gyökeréből:
    python scripts/hirdetes_letoltes_proba.py [darab]
"""

from collections import Counter, defaultdict
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlparse

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.adatbazis import kliens  # noqa: E402


DARAB = int(sys.argv[1]) if len(sys.argv) > 1 else 50

# Két letöltés között ennyit várunk: nem terheljük a kiszolgálókat.
VARAKOZAS_MP = 1.0
IDOTULLEPES_MP = 12

FEJLEC = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "hu-HU,hu;q=0.9",
}

_SCRIPT_STILUS = re.compile(
    r"<(script|style|noscript)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE
)
_TAG = re.compile(r"<[^>]+>")
_SZOKOZ = re.compile(r"\s+")


def szoveggé(html: str) -> str:
    tiszta = _SCRIPT_STILUS.sub(" ", html)
    tiszta = _TAG.sub(" ", tiszta)
    return _SZOKOZ.sub(" ", tiszta).strip()


def main() -> int:
    db = kliens()
    if not db:
        print("Nincs adatbázis-kapcsolat.")
        return 1

    valasz = (
        db.table("hirdetesek")
        .select("id, link, snippet, forras_tipus")
        .neq("link", "")
        .order("id", desc=True)
        .limit(DARAB)
        .execute()
    )
    sorok = [s for s in (valasz.data or []) if s.get("link")]
    print(f"Próba {len(sorok)} hirdetésen. Csak olvasás.\n")

    sikeres = 0
    hosszak: list[tuple[int, int]] = []
    portal_eredmeny: dict[str, Counter] = defaultdict(Counter)

    for i, sor in enumerate(sorok, start=1):
        portal = urlparse(sor["link"]).netloc.replace("www.", "")
        try:
            r = requests.get(
                sor["link"], headers=FEJLEC, timeout=IDOTULLEPES_MP
            )
            allapot = r.status_code
        except requests.RequestException as exc:
            portal_eredmeny[portal][type(exc).__name__] += 1
            print(f"[{i:3d}] {portal:28s} HIBA  {type(exc).__name__}")
            time.sleep(VARAKOZAS_MP)
            continue

        if allapot != 200:
            portal_eredmeny[portal][str(allapot)] += 1
            print(f"[{i:3d}] {portal:28s} {allapot}")
            time.sleep(VARAKOZAS_MP)
            continue

        szoveg = szoveggé(r.text)
        regi = len(sor.get("snippet") or "")
        # A hirdetésoldalak tele vannak menüvel és lábléccel; a nyers hossz
        # felső becslés, nem a tiszta hirdetésszöveg.
        hosszak.append((regi, len(szoveg)))
        sikeres += 1
        portal_eredmeny[portal]["ok"] += 1
        print(f"[{i:3d}] {portal:28s} OK    {regi:5d} -> {len(szoveg):7d}")
        time.sleep(VARAKOZAS_MP)

    print()
    print(f"Letölthető: {sikeres}/{len(sorok)}  ({100 * sikeres / max(len(sorok), 1):.0f}%)")
    if hosszak:
        regi_atlag = sum(r for r, _ in hosszak) / len(hosszak)
        uj_atlag = sum(u for _, u in hosszak) / len(hosszak)
        print(f"Átlagos hossz: {regi_atlag:.0f} -> {uj_atlag:.0f} karakter "
              f"({uj_atlag / max(regi_atlag, 1):.0f}-szeres)")

    print("\nPortálonként:")
    for portal, szamok in sorted(
        portal_eredmeny.items(), key=lambda p: -sum(p[1].values())
    ):
        reszletek = ", ".join(f"{k}={v}" for k, v in szamok.most_common())
        print(f"  {portal:32s} {reszletek}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
