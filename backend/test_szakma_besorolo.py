# -*- coding: utf-8 -*-
"""A besoroló regressziós tesztjei — VALÓDI hibákból, valódi címekkel.

MIÉRT EZ A FÁJL LÉTEZIK: 2026-07-29-én 174 teszt volt zöld, miközben a
„Konyhai kisegítő" hirdetés az „AI mérnök" szakmában ült, a „Villanyszerelő"
a „villanyóra-szerelő"-ben, az „Összeszerelő" pedig a „karbantartó"-ban.
Egyik teszt sem nézte meg, MI JÖN KI a besorolásból -- mockolt bemeneten a
logikát ellenőrizték, nem az eredményt.

Itt minden eset egy ténylegesen megtörtént félresorolás. Ha valaki átírja a
pontozást, ezek buknak el először.

Adatbázis NEM kell hozzá: a szótár itt épül fel, kézzel, kicsiben.
"""

import pytest

from backend.szakma_besorolo import Besorolo


def _besorolo() -> Besorolo:
    """Kicsi, de a valódi ütközéseket tartalmazó szótár."""
    foglalkozasok = [
        {"uri": "u:villanyszerelo", "nev": "villanyszerelő",
         "isco_kod": "7411", "alt_nevek": []},
        # Ez az a hosszabb név, ami a "Villanyszerelő" címet elvitte: a
        # "villanyóra" toldalékvágás után "villany" lesz, és a súlya nagyobb.
        {"uri": "u:villanyora", "nev": "villanyóra-szerelő",
         "isco_kod": "7411", "alt_nevek": []},
        # A "szerelő" az "összeszerelő" KÖZEPÉN is benne van.
        {"uri": "u:karbantarto", "nev": "karbantartó",
         "isco_kod": "7412", "alt_nevek": ["szerelő"]},
        {"uri": "u:osszeszerelo", "nev": "összeszerelő",
         "isco_kod": "8211", "alt_nevek": []},
        # A "takarítónő" az ESCO-ban egy NAGYON specifikus foglalkozás
        # alternatív neve.
        {"uri": "u:vidampark", "nev": "takarító vidámparkban",
         "isco_kod": "9112", "alt_nevek": ["takarítónő"]},
        {"uri": "u:targonca", "nev": "targonca vezetője",
         "isco_kod": "8344", "alt_nevek": []},
        {"uri": "u:operator", "nev": "gyári operátor",
         "isco_kod": "8219", "alt_nevek": []},
    ]
    szakmak = [
        {"id": 1, "nev": "villanyszerelő"},
        {"id": 2, "nev": "karbantartó"},
        {"id": 3, "nev": "takarító"},
        {"id": 4, "nev": "targoncavezető"},
        {"id": 5, "nev": "gyári operátor"},
        {"id": 6, "nev": "összeszerelő"},
        {"id": 7, "nev": "villanyóra-szerelő"},
    ]
    parok = [
        {"szakma_id": 1, "foglalkozas_uri": "u:villanyszerelo"},
        {"szakma_id": 2, "foglalkozas_uri": "u:karbantarto"},
        {"szakma_id": 3, "foglalkozas_uri": "u:vidampark"},
        {"szakma_id": 4, "foglalkozas_uri": "u:targonca"},
        {"szakma_id": 5, "foglalkozas_uri": "u:operator"},
        {"szakma_id": 6, "foglalkozas_uri": "u:osszeszerelo"},
        {"szakma_id": 7, "foglalkozas_uri": "u:villanyora"},
    ]
    return Besorolo(foglalkozasok, szakmak, parok)


@pytest.fixture(scope="module")
def besorolo() -> Besorolo:
    return _besorolo()


def test_pontos_egyezes_ver_a_hosszabb_nevnel(besorolo):
    """„Villanyszerelő" nem lehet villanyóra-szerelő.

    Mérve 2026-07-29: 175 hirdetés került a villanyóra-szerelőhöz, mert a
    „villanyóra" toldalékvágás után „villany" lett, és a hosszabb név
    nagyobb súlyt kapott. A cím SZÓ SZERINT egy szakma neve -- ennél
    pontosabb válasz nincs.
    """
    talalat = besorolo.besorol("Villanyszerelő")
    assert talalat is not None
    assert talalat.szakma_nev == "villanyszerelő"


def test_rovid_cimke_nem_illeszkedhet_osszetett_szo_kozepere(besorolo):
    """Az összeszerelő nem karbantartó.

    Mérve: 21 „Összeszerelő operátor" hirdetés lett karbantartó, mert a
    „szerelő" (a karbantartó ESCO-alternatívája) benne van az
    „összeszerelő"-ben. A címkének szó ELEJÉN kell megkapaszkodnia.
    """
    talalat = besorolo.besorol("Összeszerelő")
    assert talalat is not None
    assert talalat.szakma_nev == "összeszerelő"


def test_sajat_szakmanev_ver_az_esco_alternativajanal(besorolo):
    """A takarító nem vidámparki takarító.

    A „takarítónő" az ESCO-ban a „takarító vidámparkban" alternatív neve.
    Azonos súlynál a saját, kézzel gondozott szakmanevünk nyerjen.
    """
    talalat = besorolo.besorol("Részmunkaidős takarító")
    assert talalat is not None
    assert talalat.szakma_nev == "takarító"


def test_osszetett_szo_tovabbra_is_mukodik(besorolo):
    """A horgony-szabály nem törheti el a magyar összetett szavakat.

    A „targonca vezetője" címke „vezető" feltétele a „targoncavezető" szó
    KÖZEPÉN áll. Ezt meg kell fogni -- elég, ha a címke valahol (itt a
    „targon" feltétellel) szó elején megkapaszkodik.
    """
    talalat = besorolo.besorol("Targoncavezető")
    assert talalat is not None
    assert talalat.szakma_nev == "targoncavezető"


def test_specifikusabb_cimke_nyer_ha_tobbet_fed_le(besorolo):
    """A „gyári operátor" pontosabb válasz, mint a puszta „operátor"."""
    talalat = besorolo.besorol("Gyári operátor")
    assert talalat is not None
    assert talalat.szakma_nev == "gyári operátor"


def test_ekezet_szamit(besorolo):
    """Az „operátor" (gépkezelő) és az „operatőr" (kameraman) nem ugyanaz.

    Ékezet nélkül a kettő betűre azonos lenne, és a gyári operátorokat
    kamerásnak sorolná be a rendszer.
    """
    assert besorolo.besorol("Gyári operátor").szakma_nev == "gyári operátor"


def test_ismeretlen_cimre_nem_talal_ki_semmit(besorolo):
    """A „nem tudom" érvényes válasz.

    Rosszul besorolni rosszabb, mint nem besorolni: a piaci körkép egy
    téves szakmában magabiztosan hibás bért mutatna.
    """
    assert besorolo.besorol("Senior PHP Developer") is None
    assert besorolo.besorol("Áruházi munkatárs") is None


def test_minden_szakmanev_onmagara_sorolodik(besorolo):
    """Önkonzisztencia: ha a cím egy szakma neve, az a szakma jöjjön ki.

    Ez a legolcsóbb minőségmérce, mert nem kell hozzá kézi címkézés: a
    szakmanevek maguk adják az elvárt eredményt. Élesben 2026-07-29-én
    677-ből 672 (99,3%).
    """
    szakmak = ["villanyszerelő", "karbantartó", "takarító", "targoncavezető",
               "gyári operátor", "összeszerelő"]
    for nev in szakmak:
        talalat = besorolo.besorol(nev)
        assert talalat is not None, f"{nev}: nincs találat"
        assert talalat.szakma_nev == nev, f"{nev} -> {talalat.szakma_nev}"
