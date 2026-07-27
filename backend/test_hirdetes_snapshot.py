import datetime

from backend.hirdetes_snapshot import (
    elemzesi_szoveg,
    kanonikus_json,
    sha256_szoveg,
    snapshot_keszitese,
)


IDO = datetime.datetime(2026, 7, 27, 20, 0, tzinfo=datetime.timezone.utc)


def _snapshot(**feluliras):
    adatok = {
        "forras_tipus": "eures",
        "forras_azonosito": "EURES-123",
        "forras_url": "https://example.test/job/123",
        "keresesi_kulcsszo": "raktáros",
        "forras_szoveg_mezo": "description",
        "raw_payload": {"id": "EURES-123", "title": "Raktáros"},
        "raw_szoveg": "Feladatok: áruátvétel és készletkezelés.",
        "szoveg_minoseg": "teljes",
        "cim": "Raktáros",
        "nyelv": "hu",
        "gyujto": "eures-v2:test",
        "gyujtesi_futas": "test-futas",
        "begyujtve": IDO,
    }
    adatok.update(feluliras)
    return snapshot_keszitese(**adatok)


def test_payload_hash_kulcssorrendtol_fuggetlen():
    bal = {"title": "Teszt", "id": 7}
    jobb = {"id": 7, "title": "Teszt"}

    assert kanonikus_json(bal) == kanonikus_json(jobb)
    assert sha256_szoveg(kanonikus_json(bal)) == sha256_szoveg(
        kanonikus_json(jobb)
    )


def test_teljes_validalt_szoveg_elemzesre_alkalmas():
    snapshot = _snapshot()

    assert snapshot["validacios_allapot"] == "elfogadott"
    assert snapshot["listazasra_alkalmas"] is True
    assert snapshot["elemzesre_alkalmas"] is True
    assert snapshot["validacios_hibak"] == []


def test_snippet_listazhato_de_elemzesre_tiltott():
    snapshot = _snapshot(
        forras_tipus="jooble",
        forras_azonosito="jooble-123",
        forras_szoveg_mezo="snippet",
        szoveg_minoseg="snippet",
    )

    assert snapshot["validacios_allapot"] == "elfogadott"
    assert snapshot["listazasra_alkalmas"] is True
    assert snapshot["elemzesre_alkalmas"] is False
    assert "snippet_nem_hasznalhato_elemzesre" in snapshot["figyelmeztetesek"]


def test_hibas_forraselem_karantenba_kerul():
    snapshot = _snapshot(
        forras_azonosito="",
        raw_payload=[],
        raw_szoveg="",
        cim="",
    )

    assert snapshot["validacios_allapot"] == "karanten"
    assert snapshot["listazasra_alkalmas"] is False
    assert snapshot["elemzesre_alkalmas"] is False
    assert {
        "hianyzo_forras_azonosito",
        "raw_payload_nem_objektum",
        "hianyzo_cim",
        "hianyzo_raw_szoveg",
    }.issubset(snapshot["validacios_hibak"])


def test_eredeti_payload_es_szoveg_valtozatlan_marad():
    payload = {
        "id": "x",
        "description": "<p>  Eredeti\nszöveg &amp; jelölés  </p>",
        "nested": {"b": 2, "a": 1},
    }
    raw_szoveg = payload["description"]

    snapshot = _snapshot(raw_payload=payload, raw_szoveg=raw_szoveg)

    assert snapshot["raw_payload"] is payload
    assert snapshot["raw_payload"] == payload
    assert snapshot["raw_szoveg"] == raw_szoveg
    assert snapshot["raw_szoveg_sha256"] == sha256_szoveg(raw_szoveg)
    assert elemzesi_szoveg(snapshot["raw_szoveg"]) == "Eredeti szöveg & jelölés"


class _Valasz:
    def __init__(self, adat):
        self._adat = adat
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self._adat


def test_jooble_forraselem_valtozatlan_snapshot_metaadatban(monkeypatch):
    from scripts import jooble_gyujto

    nyers = {
        "id": 91,
        "title": "  Raktáros  ",
        "company": "Teszt Kft.",
        "snippet": "<b>Feladatok:</b>\n  áruátvétel &amp; leltár  ",
        "link": "https://example.test/jooble/91",
        "location": "Budapest",
        "updated": "2026-07-27T10:00:00Z",
        "salary": "",
    }
    monkeypatch.setattr(
        jooble_gyujto.requests,
        "post",
        lambda *_, **__: _Valasz({"jobs": [nyers]}),
    )
    monkeypatch.setattr(jooble_gyujto, "MAX_OLDAL", 1)

    allas = jooble_gyujto.jooble_kereses("raktáros")[0]

    assert allas["_snapshot"]["raw_payload"] is nyers
    assert allas["_snapshot"]["raw_szoveg"] == nyers["snippet"]
    assert allas["_snapshot"]["szoveg_minoseg"] == "snippet"
    assert allas["snippet"] != nyers["snippet"]


def test_jooble_snippet_kenyszeritve_sem_indit_geminit(monkeypatch):
    from scripts import jooble_gyujto

    def _tiltott_hivas(*_, **__):
        raise AssertionError("Snippet miatt nem indulhat modellhívás.")

    monkeypatch.setattr(jooble_gyujto.requests, "post", _tiltott_hivas)
    eredmeny = jooble_gyujto.keszsegek_kinyerese(
        [
            {
                "cim": "Teszt",
                "snippet": "Rövid kivonat",
                "_snapshot": {"szoveg_minoseg": "snippet"},
            }
        ],
        kenyszerit=True,
    )

    assert eredmeny == [[]]


def test_eures_nyers_forraselem_csak_kert_esetben_kerul_vissza(monkeypatch):
    from utils import eures

    nyers = {
        "id": "EURES-91",
        "title": "Raktáros",
        "description": "<p>Teljes, eredeti\nleírás.</p>",
        "employer": {"name": "Teszt Kft."},
        "locationMap": {"HU": {}},
        "availableLanguages": ["HU"],
        "positionScheduleCodes": ["FULL_TIME"],
        "creationDate": 1785110400000,
    }
    monkeypatch.setattr(
        eures.requests,
        "post",
        lambda *_, **__: _Valasz({"jvs": [nyers], "numberRecords": 1}),
    )

    allas = eures.eures_kereses(
        "raktáros",
        ["hu"],
        nyers_forras=True,
    )["allasok"][0]
    feluleti_allas = eures.eures_kereses(
        "raktáros",
        ["hu"],
    )["allasok"][0]

    assert allas["_nyers_forras"]["payload"] is nyers
    assert allas["_nyers_forras"]["szoveg"] == nyers["description"]
    assert "_nyers_forras" not in feluleti_allas
