# -*- coding: utf-8 -*-
"""MUNKAPSZICHOLÓGIAI TESZT — kérdések + determinisztikus pontozás.

Alapok (a tudásbázis forrásaiból):
- Holland érdeklődés-típusok (Corvinus tankönyv, IV. fejezet)
- Schein karrierhorgony-elmélet (uo.)
- Jóllét-blokk (Gallup 2022 + pozitív szervezetpszichológia dia)

A pontozást KÓD végzi, nem AI — az AI (Flow) csak a kiértékelő szöveget
fogalmazza majd a tudásbázisból.
"""

# ── HOLLAND-BLOKK: 6 állítás, 1-4 skála ──────────────────────
HOLLAND_SKALA = ["Egyáltalán nem", "Kicsit", "Közepesen", "Nagyon"]

HOLLAND_KERDESEK = [
    ("R", "Szívesen dolgozom kézzel, eszközökkel, gépekkel — szeretem, ha "
          "kézzelfogható az eredmény."),
    ("I", "Szeretek problémákat elemezni, a dolgok mélyére ásni, megérteni, "
          "hogyan működnek."),
    ("A", "Fontos, hogy alkothassak — ötletek, szövegek, látvány, saját "
          "elképzelések megvalósítása."),
    ("S", "Feltöltődöm, ha embereknek segíthetek, taníthatok, támogathatok."),
    ("E", "Szeretek irányítani, meggyőzni, felelősséget vállalni, célokért "
          "hajtani."),
    ("C", "Jólesik a rend, a pontos szabályok, az átlátható, jól strukturált "
          "munka."),
]

HOLLAND_NEVEK = {
    "R": "Megvalósító (gyakorlatias)",
    "I": "Kutató (elemző)",
    "A": "Alkotó (kreatív)",
    "S": "Segítő (emberközpontú)",
    "E": "Vállalkozó (irányító)",
    "C": "Rendszerező (strukturált)",
}

# ── KARRIERHORGONY-BLOKK: mi a legfontosabb a munkában? ──────
HORGONY_OPCIOK = [
    "Hogy igazi szakértője lehessek a területemnek",
    "Hogy idővel vezethessek, irányíthassak",
    "Hogy önállóan, a magam módján dolgozhassak",
    "A biztonság és a kiszámíthatóság",
    "Hogy alkothassak, újat hozhassak létre",
    "Hogy másokon segítsen a munkám",
    "A kihívás — nehéz feladatok, amiken fejlődöm",
    "Az egyensúly a munka és a magánélet között",
]

# ── JÓLLÉT-BLOKK ─────────────────────────────────────────────
ENERGIA_SKALA = ["Teljesen kimerült vagyok", "Fáradt vagyok", "Változó",
                 "Többnyire energikus vagyok"]
STRESSZ_SKALA = ["Egyáltalán nem", "Néha", "Gyakran", "Szinte állandóan"]

VALTAS_OKOK = [
    "Fejlődni szeretnék / jobb lehetőséget keresek",
    "Pályakezdő vagyok, most indulok",
    "Elfáradtam, kiégtem a mostani munkámban",
    "Rossz a munkahelyi légkör / bántóan viselkednek velem",
    "Elvesztettem a munkám / megszűnt az állásom",
    "Más okból",
]


def holland_tipus(pontok: dict) -> str:
    """A legmagasabb pontszámú típus neve (holtversenynél mindkettő)."""
    if not pontok:
        return ""
    maximum = max(pontok.values())
    nyertesek = [HOLLAND_NEVEK[k] for k, v in pontok.items() if v == maximum]
    return " + ".join(nyertesek[:2])


def jollet_jelzes(energia_idx: int, stressz_idx: int, valtas_ok: str) -> dict:
    """Determinisztikus jóllét-értékelés. Nem diagnózis — jelzés.

    Visszaad: {"cimke": rövid szöveg a profilba,
               "figyelem": True, ha kimerülés/bántalmazás jele látszik,
               "tamogato_uzenet": empatikus mondat a kiértékeléshez}
    """
    kiegett = "kiégtem" in (valtas_ok or "")
    bantalmazott = "bántóan" in (valtas_ok or "")
    kimerules = energia_idx <= 1 and stressz_idx >= 2

    if bantalmazott:
        return {
            "cimke": "megterhelő munkahelyi közeg",
            "figyelem": True,
            "tamogato_uzenet": (
                "Amit leírtál a munkahelyi légkörről, annak neve van, és nem "
                "te tehetsz róla. Az, hogy váltani szeretnél, egészséges "
                "döntés. Ha a helyzet nagyon nyomaszt, érdemes szakemberrel "
                "(pl. munkahelyi mentálhigiénés tanácsadóval, pszichológussal) "
                "is beszélned — megérdemled a támogatást."),
        }
    if kiegett or kimerules:
        return {
            "cimke": "kimerülés jelei",
            "figyelem": True,
            "tamogato_uzenet": (
                "A válaszaidból fáradtság, kimerülés látszik. Ez nem "
                "gyengeség — a kiégés a tartós túlterhelés természetes "
                "következménye. A váltás tervezésénél erre tekintettel "
                "leszünk: most nem a 'tanulj még többet', hanem a "
                "fenntartható következő lépés a cél."),
        }
    return {
        "cimke": "rendben",
        "figyelem": False,
        "tamogato_uzenet": "",
    }
