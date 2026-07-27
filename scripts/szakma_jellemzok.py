"""Egy szakmára jellemző kifejezések a hirdetésszövegekből — közvetlenül.

Nem a készségtáblából dolgozik, hanem a nyers hirdetésszövegből. Így
kimarad a kinyerés → kanonizálás → fogalom lánc, és vele az a hiba is,
amit minden lépés hozzátesz.

Az elv: egy kifejezés akkor jellemző egy szakmára, ha ANNAK a hirdetéseiben
sokkal gyakoribb, mint az összes hirdetésben átlagosan. Ami mindenhol
előfordul („versenyképes fizetés"), az egyik szakmára sem jellemző, tehát
magától kiesik — nem kell hozzá tiltólista.

Nulla modellhívás.

Futtatás a projekt gyökeréből:
    python scripts/szakma_jellemzok.py "bolti eladó" "Python fejlesztő"
"""

from collections import Counter, defaultdict
from math import log
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.keszseg_felismero import normalizal  # noqa: E402
from utils.adatbazis import kliens  # noqa: E402


MAX_SZO = 3
MIN_SZO_HOSSZ = 4

# A szakma hirdetéseinek legalább ennyi hányadában szerepeljen. Ez zárja ki
# az egyetlen munkáltató sablonszövegét, amit többször is feladtak.
MIN_ARANY = 0.03

# Abszolút alsó korlát a kis szakmákra.
MIN_ELOFORDULAS = 4

# Ennyiszer legyen gyakoribb a szakmában, mint az összes hirdetésben.
#
# A mérés szerint a jel és a zaj élesen elválik: a valódi szakmai
# kifejezések 15-40-szeres kiemelkedésűek, az álláshirdetés-töltelék
# („amit kínálunk", „nyertes pályázat", „looking") 3-5-szörös. A küszöb
# a kettő közé esik.
MIN_KIEMELKEDES = 8.0

TOP = 30


def lapozva(db, tabla: str, mezok: str, rendez: str) -> list:
    sorok, kezdet = [], 0
    while True:
        valasz = (
            db.table(tabla).select(mezok).order(rendez)
            .range(kezdet, kezdet + 999).execute()
        )
        adag = valasz.data or []
        sorok.extend(adag)
        if len(adag) < 1000:
            return sorok
        kezdet += 1000


def ngramok(szoveg: str) -> set[str]:
    szavak = [
        szo for szo in normalizal(szoveg).split() if len(szo) >= MIN_SZO_HOSSZ
    ]
    talalt = set()
    for hossz in range(1, MAX_SZO + 1):
        for kezdet in range(len(szavak) - hossz + 1):
            talalt.add(" ".join(szavak[kezdet : kezdet + hossz]))
    return talalt


def main() -> int:
    kert_szakmak = sys.argv[1:] or ["bolti eladó", "Python fejlesztő"]

    db = kliens()
    if not db:
        print("Nincs adatbázis-kapcsolat.")
        return 1

    print("Hirdetések betöltése…")
    hirdetesek = lapozva(db, "hirdetesek", "id, szakma_id, cim, snippet", "id")
    szakmak = {s["id"]: s["nev"] for s in lapozva(db, "szakmak", "id, nev", "id")}

    # Cégnevek: minden szakmában zajként jelennének meg.
    cegnevek = set()
    for sor in lapozva(db, "cegek", "id, nev", "id"):
        tiszta = normalizal(sor.get("nev") or "")
        if tiszta:
            cegnevek.add(tiszta)
            cegnevek.update(tiszta.split())

    print(f"  {len(hirdetesek)} hirdetés, {len(szakmak)} szakma, "
          f"{len(cegnevek)} cégnév-elem\n")

    szakma_ngramjai: dict[int, Counter] = defaultdict(Counter)
    szakma_darab: Counter = Counter()
    ossz_ngram: Counter = Counter()

    for sor in hirdetesek:
        szid = sor.get("szakma_id")
        if not szid:
            continue
        kifejezesek = ngramok(f"{sor.get('cim') or ''} {sor.get('snippet') or ''}")
        szakma_darab[szid] += 1
        szakma_ngramjai[szid].update(kifejezesek)
        ossz_ngram.update(kifejezesek)

    ossz_hirdetes = sum(szakma_darab.values())

    for kert in kert_szakmak:
        szid = next(
            (i for i, nev in szakmak.items() if nev.casefold() == kert.casefold()),
            None,
        )
        if szid is None or not szakma_darab.get(szid):
            print(f"=== {kert}: nincs adat\n")
            continue

        darab = szakma_darab[szid]
        pontok = []
        for kifejezes, elofordulas in szakma_ngramjai[szid].items():
            if elofordulas < MIN_ELOFORDULAS:
                continue
            if any(szo in cegnevek for szo in kifejezes.split()):
                continue
            szakmai_arany = elofordulas / darab
            if szakmai_arany < MIN_ARANY:
                continue
            altalanos_arany = ossz_ngram[kifejezes] / ossz_hirdetes
            kiemelkedes = szakmai_arany / max(altalanos_arany, 1e-9)
            if kiemelkedes < MIN_KIEMELKEDES:
                continue
            # Gyakoriság ÉS kiemelkedés együtt. Külön-külön egyik sem jó:
            # a gyakoriság a mindenhol előforduló tölteléket hozza fel, a
            # kiemelkedés pedig egyetlen munkáltató sablonszövegét, mert ott
            # a mutató telítődik.
            pont = szakmai_arany * log(kiemelkedes)
            pontok.append((pont, szakmai_arany, kiemelkedes, elofordulas, kifejezes))

        pontok.sort(reverse=True)
        print(f"=== {szakmak[szid]}  ({darab} hirdetés)")
        for _pont, arany, kiemelkedes, elofordulas, kifejezes in pontok[:TOP]:
            print(f"  {100 * arany:5.1f}%  x{kiemelkedes:5.1f}  "
                  f"({elofordulas:4d})  {kifejezes}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
