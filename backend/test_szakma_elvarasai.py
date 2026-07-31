# -*- coding: utf-8 -*-
"""A „Mit várnak el?" kérdés adata a hirdetésekből.

A hirdetések tárolt szövege medián 269 karakter (forráskorlát), ezért a
kinyert tételek egy része félbevágott mondat. Ezek nem kerülhetnek a
felhasználó elé „ezt várják el" felirattal -- ezt méri ez a fájl.
"""

import pytest

from utils.adatbazis import _hasznalhato_tetel, szakma_elvarasai


@pytest.mark.parametrize(
    "szoveg",
    [
        "Árufeltöltés és készletkezelés",
        "Pénztárgép kezelés",
        "csapatszellem, motiváció",
        "beérkező áruk átvétele",
        "Vásárlók magas szintű kiszolgálása és az üzlet rendezettsége",
    ],
)
def test_onallo_tetel_atmegy(szoveg):
    assert _hasznalhato_tetel(szoveg) is True


@pytest.mark.parametrize(
    "szoveg, miert",
    [
        (
            "Értékeinkkel összhangban hozzájárulsz közös, valamint a vállalat",
            "névelő + egy szó a végén: ott vágták el a mondatot",
        ),
        ("A fentiekhez", "az előző mondat folytatása, nem önálló elvárás"),
        (
            "Lehetőséged lesz minden pillanatban magas szintű",
            "jelzővel végződik, hiányzik a jelzett szó",
        ),
        ("és a napi zárás", "kötőszóval kezdődik"),
        ("Árufeltöltés,", "vesszővel végződik, tehát folytatódna"),
        ("Bolt", "túl rövid ahhoz, hogy elvárás legyen"),
        ("x" * 200, "túl hosszú: ez már a hirdetés fele"),
        ("", "üres"),
    ],
)
def test_csonka_tetel_kiesik(szoveg, miert):
    assert _hasznalhato_tetel(szoveg) is False, miert


def test_gyakorisag_szerint_rangsorol_es_szamol(monkeypatch):
    """Ami egyetlen hirdetésből jön, az nem piaci elvárás, hanem egy cég szövege.

    Ezért minden tétel mellett ott a `hirdetes_db` -- enélkül a felhasználó
    egy véletlen mondatot hinne általános követelménynek.
    """
    import utils.adatbazis as adatbazis

    sorok = [
        {"hirdetes_id": 1, "szekcio": "feladat", "szoveg": "Pénztárgép kezelés"},
        {"hirdetes_id": 2, "szekcio": "feladat", "szoveg": "pénztárgép kezelés"},
        {"hirdetes_id": 3, "szekcio": "feladat", "szoveg": "Árufeltöltés és készletezés"},
        {"hirdetes_id": 4, "szekcio": "elvaras", "szoveg": "csapatszellem, motiváció"},
        # Ez csonka: ki kell esnie.
        {"hirdetes_id": 5, "szekcio": "elvaras", "szoveg": "Értékeinkkel a"},
    ]

    class _Lekerdezes:
        def select(self, *_): return self
        def eq(self, *_): return self
        def in_(self, *_): return self
        def limit(self, *_): return self
        def execute(self): return type("V", (), {"data": sorok})()

    class _Db:
        def table(self, *_): return _Lekerdezes()

    monkeypatch.setattr(adatbazis, "kliens", lambda: _Db())
    monkeypatch.setattr(adatbazis, "szakma_id_nevbol", lambda _: 601)

    eredmeny = szakma_elvarasai("eladó")

    assert eredmeny["feladatok"][0] == {
        "szoveg": "Pénztárgép kezelés",
        "hirdetes_db": 2,
    }
    assert eredmeny["feladatok"][1]["hirdetes_db"] == 1
    assert eredmeny["elvarasok"] == [
        {"szoveg": "csapatszellem, motiváció", "hirdetes_db": 1}
    ]
    # A csonka tétel hirdetése nem számít forrásnak.
    assert eredmeny["forras_hirdetes"] == 4


def test_adatbazis_nelkul_ures_listat_ad(monkeypatch):
    """Hiányzó adat nem hiba: a hívó dolga eldönteni, hogy baj-e."""
    import utils.adatbazis as adatbazis

    monkeypatch.setattr(adatbazis, "kliens", lambda: None)
    eredmeny = szakma_elvarasai("eladó")

    assert eredmeny == {"elvarasok": [], "feladatok": [], "forras_hirdetes": 0}


def test_a_szuro_nehany_ep_tetelt_is_kidob():
    """Ez vállalt csere, nem véletlen -- ezért van róla teszt.

    A „névelő + egy szó a végén" szabály kidobja az ép „...rendben tartása a
    boltban" alakot is. Inkább essen ki egy jó tétel, mint hogy egy
    félbevágott mondat jelenjen meg „ezt várják el" felirattal: az elsőt a
    felhasználó észre sem veszi, a másodikon elbizonytalanodik az egész
    adatban.
    """
    assert _hasznalhato_tetel("A munkakörnyezet rendben tartása a boltban") is False
