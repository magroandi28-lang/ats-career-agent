"""A hirdetésbontás tesztjei — hálózat és adatbázis nélkül.

A minták valódi hirdetésekből származnak, rövidítve.
"""

from backend.hirdetes_bontas import bontas, van_szerkezet


SPAR = (
    "XIII. kerület Spar Partner üzletünkbe keresünk kollégákat az alábbi "
    "pozícióba: Csemegepultos Feladatok ~Vásárlók udvarias és szakszerű "
    "kiszolgálása ~Munkakörnyezet tisztán tartása Elvárások ~Szorgalmas, "
    "megbízható munkatárs vagy ~Jól dolgozol csapatban"
)


def _szekcio(elemek, nev):
    return [szoveg for szekcio, szoveg in elemek if szekcio == nev]


def test_a_szekciok_szetvalnak():
    elemek = bontas(SPAR)

    feladatok = _szekcio(elemek, "feladat")
    elvarasok = _szekcio(elemek, "elvaras")

    assert "Vásárlók udvarias és szakszerű kiszolgálása" in feladatok
    assert "Munkakörnyezet tisztán tartása" in feladatok
    assert any("Szorgalmas" in e for e in elvarasok)
    # A feladat nem szivároghat át az elvárások közé és fordítva.
    assert not any("Vásárlók" in e for e in elvarasok)


def test_a_ceg_bemutatkozasa_nem_feladat():
    """A szekciócím ELŐTTI rész sosem feladat, akármit is tartalmaz."""
    elemek = bontas(SPAR)
    assert any(
        "Spar Partner" in szoveg
        for szekcio, szoveg in elemek
        if szekcio == "egyeb"
    )


def test_jeloletlen_felsorolas_is_szetvalik():
    """Ahol nincs ~ jel, ott a kisbetű utáni nagybetű jelzi az új tételt."""
    szoveg = (
        "Feladatok Vásárlók kedves kiszolgálása Pénztárkezelés majd "
        "Árufeltöltés, polcrendezés"
    )
    feladatok = _szekcio(bontas(szoveg), "feladat")
    assert "Vásárlók kedves kiszolgálása" in feladatok
    assert "Árufeltöltés, polcrendezés" in feladatok


def test_ket_nagybetus_tetel_egyben_marad():
    """Ismert korlát, szándékos: a tulajdonnév védelme az előbbre való.

    A „Pénztárkezelés Árufeltöltés" és a „Spar Partner" szövegből
    megkülönböztethetetlen. Inkább összevonunk két elvárást, mint hogy
    egy cégnevet kettévágjunk.
    """
    feladatok = _szekcio(bontas("Feladatok Pénztárkezelés Árufeltöltés"), "feladat")
    assert feladatok == ["Pénztárkezelés Árufeltöltés"]


def test_tulajdonnev_nem_vagja_kette_a_tetelt():
    """A Nagybetű+Nagybetű nem határ: „Spar Partner" egyben marad."""
    szoveg = "Feladatok ~Kiszolgálás a Spar Partner üzletben minden nap"
    feladatok = _szekcio(bontas(szoveg), "feladat")
    assert any("Spar Partner" in e for e in feladatok)


def test_amit_kinalunk_kulon_szekcioba_kerul():
    """A bér és a műszak nem elvárás -- nem hiányozhat egy CV-ből."""
    szoveg = (
        "Feladatok ~Áruk összekészítése Amit kínálunk: ~Kezdő átlagos bruttó "
        "jövedelem 342 500 Ft ~Rugalmas, változó műszakok"
    )
    elemek = bontas(szoveg)
    ajanlat = _szekcio(elemek, "ajanlat")

    assert any("342 500" in e for e in ajanlat)
    assert any("műszak" in e for e in ajanlat)
    assert not any("műszak" in e for e in _szekcio(elemek, "elvaras"))


def test_a_ber_akkor_is_ajanlat_ha_az_elvarasok_kozt_all():
    """Sok hirdetés a bért az elvárások közé írja -- onnan „hiányozna" a CV-ből."""
    szoveg = (
        "Elvárások ~Kereskedelmi végzettség ~Bolti eladó pozícióban elérhető "
        "havi bruttó fizetés 342 500 Ft ~Utazási költségtérítés"
    )
    elemek = bontas(szoveg)

    assert any("végzettség" in e for e in _szekcio(elemek, "elvaras"))
    assert any("342 500" in e for e in _szekcio(elemek, "ajanlat"))
    assert not any("342 500" in e for e in _szekcio(elemek, "elvaras"))


def test_a_cegjellemzo_szoveg_kulturaba_kerul():
    """Nem zaj: ebből derül ki, milyen munkahelyre készül az ember.

    De nem is feladat -- a „nagyszerű élményt nyújtani" nem elvégzendő
    munka, tehát nem hiányozhat egy CV-ből.
    """
    szoveg = (
        "Feladatok ~Áruk összekészítése ~Szeretnél felelős lenni egy "
        "nagyszerű csapatért? ~Raktári rend fenntartása"
    )
    elemek = bontas(szoveg)

    feladatok = _szekcio(elemek, "feladat")
    kultura = _szekcio(elemek, "kultura")

    assert "Áruk összekészítése" in feladatok
    assert "Raktári rend fenntartása" in feladatok
    assert any("nagyszerű" in e for e in kultura)
    assert not any("nagyszerű" in e for e in feladatok)


def test_portal_metaadat_kiesik():
    szoveg = "Feladatok ~Apply by 15-Aug-2026 ~Working hours 40 ~Árufeltöltés"
    feladatok = _szekcio(bontas(szoveg), "feladat")
    assert not any("Apply by" in e for e in feladatok)
    assert not any("Working hours" in e for e in feladatok)


def test_csonka_szoveg_nem_hasal_el():
    assert bontas("") == []
    assert bontas(None) == []
    # A csonkajelek lekerülnek, a maradék pedig túl rövid tételnek.
    assert bontas("...polc...") == []


def test_van_szerkezet_jelzi_a_szekciocimet():
    assert van_szerkezet(SPAR)
    assert not van_szerkezet("Eladót keresünk azonnali kezdéssel Budapesten.")
