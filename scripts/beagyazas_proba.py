"""Megnézi, hogy a helyben futó beágyazó modell érti-e a magyar szakmai nyelvet.

Nem csak a kívánt egyezéseket méri, hanem a VESZÉLYES párokat is: ahol a
beágyazás összeköthet olyat, ami valójában nem ugyanaz. A szótár azzal
hibázik, hogy nem talál meg valamit; a beágyazás azzal, hogy túl sokat köt
össze. Mindkettőt látni kell, mielőtt bármit építünk rá.

Előfeltétel: fut az Ollama, és le van töltve egy beágyazó modell.
    ollama pull bge-m3

Futtatás a projekt gyökeréből:
    python scripts/beagyazas_proba.py
"""

import sys

import requests


OLLAMA = "http://localhost:11434/api/embed"
MODELL = "bge-m3"

# (szöveg A, szöveg B, elvárás) -- az elvárás csak a kiértékeléshez kell.
PAROK = [
    # Ezeknek KÖZEL kell lenniük: ugyanaz a munka, más szavakkal.
    ("vevőkkel foglalkozás", "vásárlók kiszolgálása", "kozel"),
    ("áruk kirakása", "árufeltöltés és rendezés", "kozel"),
    ("pénztárazás", "pénztárgép kezelése", "kozel"),
    ("kasszáztam a boltban", "pénztárkezelés", "kozel"),
    ("REST API fejlesztés", "backend fejlesztés", "kozel"),
    ("targoncával dolgoztam", "targoncavezetés", "kozel"),
    # Ezeknek TÁVOL kell lenniük: külön szakma vagy ellentétes irány.
    ("vevőkkel foglalkozás", "targoncavezetés", "tavol"),
    ("bolti eladó", "raktáros", "tavol"),
    ("pénztárgép kezelése", "hegesztés", "tavol"),
    # A csapda: az egyik eladás, a másik vétel -- a modell összekötheti.
    ("értékesítés", "vásárlás", "tavol"),
    ("árut adok el", "árut veszek", "tavol"),
]


def beagyaz(szovegek: list[str]) -> list[list[float]]:
    valasz = requests.post(
        OLLAMA, json={"model": MODELL, "input": szovegek}, timeout=120
    )
    valasz.raise_for_status()
    return valasz.json()["embeddings"]


def hasonlosag(a: list[float], b: list[float]) -> float:
    szorzat = sum(x * y for x, y in zip(a, b))
    hossz_a = sum(x * x for x in a) ** 0.5
    hossz_b = sum(y * y for y in b) ** 0.5
    return szorzat / (hossz_a * hossz_b) if hossz_a and hossz_b else 0.0


def main() -> int:
    szovegek = sorted({szo for par in PAROK for szo in par[:2]})
    try:
        vektorok = dict(zip(szovegek, beagyaz(szovegek)))
    except requests.RequestException as exc:
        print(f"Az Ollama nem válaszolt: {exc}")
        print("Fut az Ollama? Letöltötted a modellt? (ollama pull bge-m3)")
        return 1

    minta = next(iter(vektorok.values()))
    print(f"Modell: {MODELL}   vektorhossz: {len(minta)}\n")

    kozeli, tavoli = [], []
    for elso, masodik, elvaras in PAROK:
        ertek = hasonlosag(vektorok[elso], vektorok[masodik])
        (kozeli if elvaras == "kozel" else tavoli).append(ertek)
        jel = "KÖZEL" if elvaras == "kozel" else "távol"
        print(f"  {ertek:.3f}  [{jel}]  {elso!r} ↔ {masodik!r}")

    print()
    print(f"Egyezniük kellene -- legkisebb hasonlóság: {min(kozeli):.3f}")
    print(f"Különbözniük kellene -- legnagyobb:        {max(tavoli):.3f}")
    if min(kozeli) > max(tavoli):
        print("\nA két csoport SZÉTVÁLIK: van olyan küszöb, ami helyesen dönt.")
    else:
        print("\nA két csoport ÁTFED: nincs olyan küszöb, ami mindet eltalálná.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
