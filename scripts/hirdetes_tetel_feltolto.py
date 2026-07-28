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

from backend.hirdetes_snapshot import (  # noqa: E402
    elemzesi_szoveg,
    forrasbizonyitek_keresese,
    gyujto_verzio,
)
from backend.hirdetes_bontas import bontas  # noqa: E402
from backend.keszseg_felismero import normalizal  # noqa: E402
from utils.adatbazis import (  # noqa: E402
    kliens,
    osszes_sor,
    snapshotok_kapuval,
)


ADAG = 500
FELDOLGOZO_VERZIO = gyujto_verzio("hirdetes-tetel")


def _mar_feldolgozott(db) -> set[int]:
    """Mely snapshotokhoz van már bizonyítható V2 tétel."""
    idk: set[int] = set()
    kezdet = 0
    while True:
        valasz = (
            db.table("hirdetes_tetel").select("snapshot_id")
            .order("snapshot_id").range(kezdet, kezdet + 999).execute()
        )
        adag = valasz.data or []
        idk.update(sor["snapshot_id"] for sor in adag if sor.get("snapshot_id"))
        if len(adag) < 1000:
            return idk
        kezdet += 1000


def tetelsorok_keszitese(
    hirdetesek: list[dict],
    kihagyando_snapshot_idk: set[int] | None = None,
) -> tuple[list[dict], Counter, int]:
    """Bizonyítható, insert-only V2 tételsorok előállítása."""

    kihagyando = kihagyando_snapshot_idk or set()
    sorok: list[dict] = []
    szekcio_szamlalo: Counter = Counter()
    szerkezettel = 0

    for hirdetes in hirdetesek:
        if hirdetes["snapshot_id"] in kihagyando:
            continue
        raw_szoveg = hirdetes.get("raw_szoveg") or ""
        elemek = bontas(elemzesi_szoveg(raw_szoveg))
        if any(szekcio != "egyeb" for szekcio, _ in elemek):
            szerkezettel += 1

        latott: set[tuple[str, str]] = set()
        for szekcio, tetel in elemek:
            bizonyitek = forrasbizonyitek_keresese(raw_szoveg, tetel)
            if bizonyitek is None:
                continue
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
                "snapshot_id": hirdetes["snapshot_id"],
                "feldolgozo_verzio": FELDOLGOZO_VERZIO,
                **bizonyitek,
            })
    return sorok, szekcio_szamlalo, szerkezettel


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
        "id,hirdetes_id,forras_tipus,forras_azonosito,"
        "forras_szoveg_mezo,raw_payload,raw_szoveg,szoveg_minoseg,"
        "validacios_allapot,listazasra_alkalmas,"
        "elemzesre_alkalmas,begyujtve",
    )
    hirdetes_idk = [hirdetes["id"] for hirdetes in hirdetesek]
    # A legfrissebb verziót választjuk ki először. Ha az karanténos vagy
    # nem teljes, egy régebbi elfogadott snapshot sem kerülhet a helyére.
    snapshotok = snapshotok_kapuval(
        snapshot_sorok,
        hirdetes_idk,
        elemzeshez=True,
    )
    hirdetesek = [
        {
            **hirdetes,
            "snapshot_id": snapshotok[hirdetes["id"]]["id"],
            "raw_szoveg": snapshotok[hirdetes["id"]]["raw_szoveg"],
        }
        for hirdetes in hirdetesek
        if hirdetes["id"] in snapshotok
    ]
    print(f"  {len(hirdetesek)} validált, teljes szövegű hirdetés")

    kihagyando = _mar_feldolgozott(db)
    if kihagyando:
        print(f"  {len(kihagyando)} snapshot már fel van dolgozva")

    sorok, szekcio_szamlalo, szerkezettel = tetelsorok_keszitese(
        hirdetesek,
        kihagyando,
    )

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
