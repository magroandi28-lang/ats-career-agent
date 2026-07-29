# -*- coding: utf-8 -*-
"""A CV-ből javasolt célmunkakör tesztjei.

Adatbázis nélkül futnak: a szótár itt épül fel, kézzel, kicsiben.
"""

import pytest

from backend import cv_szakma_javaslat
from backend.szakma_besorolo import Besorolo


@pytest.fixture(autouse=True)
def kis_besorolo(monkeypatch):
    foglalkozasok = [
        {"uri": "u:elado", "nev": "bolti eladó", "isco_kod": "5223",
         "alt_nevek": []},
        {"uri": "u:penztaros", "nev": "pénztáros", "isco_kod": "5230",
         "alt_nevek": []},
        {"uri": "u:arufeltolto", "nev": "árufeltöltő", "isco_kod": "9334",
         "alt_nevek": ["kereskedelmi árufeltöltő"]},
        {"uri": "u:fejleszto", "nev": "Python fejlesztő", "isco_kod": "2512",
         "alt_nevek": []},
    ]
    szakmak = [
        {"id": 1, "nev": "bolti eladó"},
        {"id": 2, "nev": "pénztáros"},
        {"id": 3, "nev": "árufeltöltő"},
        {"id": 4, "nev": "Python fejlesztő"},
    ]
    parok = [
        {"szakma_id": 1, "foglalkozas_uri": "u:elado"},
        {"szakma_id": 2, "foglalkozas_uri": "u:penztaros"},
        {"szakma_id": 3, "foglalkozas_uri": "u:arufeltolto"},
        {"szakma_id": 4, "foglalkozas_uri": "u:fejleszto"},
    ]
    monkeypatch.setattr(
        cv_szakma_javaslat, "_besorolo", Besorolo(foglalkozasok, szakmak, parok)
    )


def test_a_leggyakoribb_pozicio_kerul_elore():
    """A CV-ben többször szereplő munkakör az erősebb javaslat."""
    cv = (
        "Németh Éva\n"
        "Bolti eladó\n"
        "MUNKATAPASZTALAT\n"
        "Bolti eladó - Tesco Hipermarket, 2019-2023\n"
        "Pénztáros - Spar, 2016-2019\n"
    )
    javaslatok = cv_szakma_javaslat.celmunkakor_javaslatok(cv)
    assert javaslatok[0]["szakma"] == "bolti eladó"
    assert javaslatok[0]["elofordulas"] == 2


def test_a_cegnev_es_evszam_nem_nyomja_el_a_munkakort():
    """„Bolti eladó - Tesco Hipermarket, 2019-2023" -> bolti eladó.

    A pozíciónév a sor elején áll; ha a teljes sorra illesztenénk, a hosszú
    cégnév és az évszám miatt kiesne.
    """
    javaslatok = cv_szakma_javaslat.celmunkakor_javaslatok(
        "Bolti eladó - Tesco Hipermarket, 2019-2023"
    )
    assert javaslatok
    assert javaslatok[0]["szakma"] == "bolti eladó"


def test_a_vegzettseg_nem_munkakor():
    """A „Kereskedelmi szakközépiskola" sorból árufeltöltő lett.

    Egy iskolanév nem pozíció. Mérve 2026-07-29-én, valódi minta-CV-n.
    """
    assert cv_szakma_javaslat.celmunkakor_javaslatok(
        "VÉGZETTSÉG\nKereskedelmi szakközépiskola"
    ) == []


def test_ha_nincs_felismerheto_pozicio_akkor_kerdezni_kell():
    """Üres lista = „nem tudom". Ilyenkor a felhasználót kell megkérdezni,
    nem tippelni. Rosszul javasolni rosszabb, mint nem javasolni."""
    assert cv_szakma_javaslat.celmunkakor_javaslatok(
        "Ide semmi hasznos nem került, csak egy mondat a motivációmról."
    ) == []
    assert cv_szakma_javaslat.celmunkakor_javaslatok("") == []


def test_a_bizonyitek_a_cv_sajat_sora():
    """Ami a javaslatot hozta, azt vissza kell tudni mutatni -- különben a
    felhasználó nem tudja eldönteni, jó-e."""
    javaslatok = cv_szakma_javaslat.celmunkakor_javaslatok(
        "Python fejlesztő - Ericsson, 2020-2024"
    )
    assert javaslatok[0]["bizonyitek"] == "Python fejlesztő - Ericsson, 2020-2024"
