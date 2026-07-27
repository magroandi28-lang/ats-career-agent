"""A hirdetésekből kinyert tételek feltöltése.

A `hirdetes_tetel` tábla származtatott: kizárólag validált, teljes
`hirdetes_snapshot.raw_szoveg` alapján készül. A listázási snippet ebbe a
rétegbe nem kerülhet.

Alapból csak azokat a hirdetéseket dolgozza fel, amikhez még nincs tétel.
A régi adatok védelmében a korábbi, törlő `--ujra` mód le van tiltva.

Nulla modellhívás.

Futtatás a projekt gyökeréből:
    python scripts/hirdetes_tetel_feltolto.py
"""

from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.hirdetes_snapshot import elemzesi_szoveg  # noqa: E402
from backend.hirdetes_bontas import bontas  # noqa: E402
from backend.keszseg_felismero import normalizal  # noqa: E402
from utils.adatbazis import kliens, osszes_sor  # noqa: E402


ADAG = 500


def _mar_feldolgozott(db) -> set[int]:
    """Mely hirdetésekhez van már tétel."""
    idk: set[int] = set()
    kezdet = 0
    while True:
        valasz = (
            db.table("hirdetes_tetel").select("hirdetes_id")
            .order("hirdetes_id").range(kezdet, kezdet + 999).execute()
        )
        adag = valasz.data or []
        idk.update(sor["hirdetes_id"] for sor in adag)
        if len(adag) < 1000:
            return idk
        kezdet += 1000


def main() -> int:
    ujra = "--ujra" in sys.argv
    if ujra:
        print(
            "A --ujra mód le van tiltva: régi hirdetéstételt nem törlünk "
            "és nem írunk felül."
        )
        return 2

    db = kliens()
    if not db:
        print("Nincs adatbázis-kapcsolat.")
        return 1

    print("Hirdetések betöltése…")
    hirdetesek = osszes_sor("hirdetesek", "id, szakma_id, cim")
    snapshot_sorok = osszes_sor(
        "hirdetes_snapshot",
        "id,hirdetes_id,raw_szoveg,elemzesre_alkalmas",
    )
    # Az id növekvő, ezért az utolsó érték a legfrissebb alkalmas snapshot.
    snapshotok = {
        sor["hirdetes_id"]: sor
        for sor in snapshot_sorok
        if sor.get("hirdetes_id") and sor.get("elemzesre_alkalmas") is True
    }
    hirdetesek = [
        {
            **hirdetes,
            "raw_szoveg": snapshotok[hirdetes["id"]]["raw_szoveg"],
        }
        for hirdetes in hirdetesek
        if hirdetes["id"] in snapshotok
    ]
    print(f"  {len(hirdetesek)} validált, teljes szövegű hirdetés")

    kihagyando = _mar_feldolgozott(db)
    if kihagyando:
        print(f"  {len(kihagyando)} hirdetés már fel van dolgozva")

    sorok: list[dict] = []
    szekcio_szamlalo: Counter = Counter()
    szerkezettel = 0

    for hirdetes in hirdetesek:
        if hirdetes["id"] in kihagyando:
            continue
        szoveg = (
            f"{hirdetes.get('cim') or ''} "
            f"{elemzesi_szoveg(hirdetes.get('raw_szoveg') or '')}"
        )
        elemek = bontas(szoveg)
        if any(szekcio != "egyeb" for szekcio, _ in elemek):
            szerkezettel += 1

        # Hirdetésen belül egyedi: a táblán egyedi index is védi, de itt
        # olcsóbb kiszűrni, mint ütközésre futni.
        latott: set[tuple[str, str]] = set()
        for szekcio, tetel in elemek:
            kulcs = (szekcio, normalizal(tetel))
            if not kulcs[1] or kulcs in latott:
                continue
            latott.add(kulcs)
            szekcio_szamlalo[szekcio] += 1
            sorok.append({
                "hirdetes_id": hirdetes["id"],
                "szakma_id": hirdetes.get("szakma_id"),
                "szekcio": szekcio,
                "szoveg": tetel,
                "normalizalt": kulcs[1],
            })

    if not sorok:
        print("\nNincs feldolgozandó hirdetés.")
        return 0

    print(f"\nKinyert tétel: {len(sorok)}")
    for szekcio, darab in szekcio_szamlalo.most_common():
        print(f"  {szekcio:9s} {darab:7d}")
    print(f"Kimondott szekcióval: {szerkezettel} hirdetés")

    print("\nBeírás…")
    for kezdet in range(0, len(sorok), ADAG):
        db.table("hirdetes_tetel").insert(sorok[kezdet : kezdet + ADAG]).execute()
        print(f"  {min(kezdet + ADAG, len(sorok))}/{len(sorok)}", end="\r")
    print()
    print("KÉSZ.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
