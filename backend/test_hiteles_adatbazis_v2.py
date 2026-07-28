import inspect
from pathlib import Path

import pytest

from scripts.hirdetes_tetel_feltolto import tetelsorok_keszitese
from utils.adatbazis import (
    hiteles_szarmasztott_sorok,
    snapshotok_kapuval,
)


GYOKER = Path(__file__).resolve().parent.parent
MIGRACIO = (
    GYOKER
    / "supabase"
    / "migrations"
    / "20260728012000_v2_szarmasztott_adat_proveniencia.sql"
)


def _snapshot(
    *,
    azonosito: int,
    hirdetes_id: int = 7,
    begyujtve: str,
    listazhato: bool = True,
    elemezheto: bool = True,
) -> dict:
    return {
        "id": azonosito,
        "hirdetes_id": hirdetes_id,
        "forras_tipus": "portal",
        "raw_szoveg": "Feladatok: áruátvétel és leltár.",
        "szoveg_minoseg": "teljes",
        "validacios_allapot": (
            "elfogadott" if listazhato else "karanten"
        ),
        "listazasra_alkalmas": listazhato,
        "elemzesre_alkalmas": elemezheto,
        "begyujtve": begyujtve,
    }


def test_legujabb_snapshot_dont_es_csak_utana_jon_a_kapu():
    regi_jo = _snapshot(
        azonosito=10,
        begyujtve="2026-07-27T10:00:00+00:00",
    )
    uj_karanten = _snapshot(
        azonosito=11,
        begyujtve="2026-07-28T10:00:00+00:00",
        listazhato=False,
        elemezheto=False,
    )

    eredmeny = snapshotok_kapuval(
        [regi_jo, uj_karanten],
        [7],
        elemzeshez=True,
    )

    assert eredmeny == {}


def test_snapshot_nelkuli_legacy_listazhato_de_nem_elemezheto():
    listazas = snapshotok_kapuval(
        [],
        [7],
        elemzeshez=False,
        legacy_listazhato=True,
    )
    elemzes = snapshotok_kapuval([], [7], elemzeshez=True)

    assert listazas[7]["legacy_snapshot_nelkuli"] is True
    assert listazas[7]["elemzesre_alkalmas"] is False
    assert elemzes == {}


def test_korabban_teljesnek_jelolt_hibas_eures_snapshot_is_kiesik():
    hibas = {
        **_snapshot(
            azonosito=12,
            begyujtve="2026-07-28T10:00:00+00:00",
        ),
        "forras_tipus": "eures",
        "forras_azonosito": "EURES-12",
        "forras_szoveg_mezo": "description",
        "raw_payload": {
            "id": "EURES-12",
            "title": "Raktáros",
            "description": "Másik szöveg.",
        },
    }

    assert snapshotok_kapuval(
        [hibas],
        [7],
        elemzeshez=True,
    ) == {}


def test_legacy_szarmasztott_sor_kesobbi_snapshotbol_sem_lesz_hiteles():
    snapshot = _snapshot(
        azonosito=21,
        begyujtve="2026-07-28T10:00:00+00:00",
    )
    legacy = {
        "hirdetes_id": 7,
        "keszseg_id": 3,
        "snapshot_id": None,
        "feldolgozo_verzio": None,
        "forras_bizonyitek": None,
        "forras_bizonyitek_kezdete": None,
        "forras_bizonyitek_vege": None,
    }

    assert hiteles_szarmasztott_sorok([legacy], {7: snapshot}) == []


def test_csak_a_legujabb_snapshot_pontos_bizonyiteka_hiteles():
    raw = "Feladatok: áruátvétel és leltár."
    snapshot = _snapshot(
        azonosito=22,
        begyujtve="2026-07-28T11:00:00+00:00",
    )
    kezdet = raw.index("áruátvétel")
    veg = kezdet + len("áruátvétel és leltár")
    jo = {
        "hirdetes_id": 7,
        "snapshot_id": 22,
        "feldolgozo_verzio": "teszt-v2:abc",
        "forras_bizonyitek": raw[kezdet:veg],
        "forras_bizonyitek_kezdete": kezdet,
        "forras_bizonyitek_vege": veg,
    }
    rossz_snapshot = {**jo, "snapshot_id": 20}
    rossz_bizonyitek = {**jo, "forras_bizonyitek": "kitalált szöveg"}

    assert hiteles_szarmasztott_sorok([jo], {7: snapshot}) == [jo]
    assert hiteles_szarmasztott_sorok(
        [rossz_snapshot, rossz_bizonyitek],
        {7: snapshot},
    ) == []


def test_v2_tetelsor_minden_kotelezo_provenienciat_tartalmaz():
    raw = (
        "<p>Feladatok:</p> "
        "<p>áruátvétel és készletkezelés; leltár készítése naponta</p>"
    )

    sorok, _, _ = tetelsorok_keszitese([
        {
            "id": 7,
            "szakma_id": 2,
            "snapshot_id": 31,
            "raw_szoveg": raw,
        }
    ])

    assert sorok
    for sor in sorok:
        assert sor["snapshot_id"] == 31
        assert sor["feldolgozo_verzio"]
        kezdet = sor["forras_bizonyitek_kezdete"]
        veg = sor["forras_bizonyitek_vege"]
        assert raw[kezdet:veg] == sor["forras_bizonyitek"]


def test_adatbazis_trigger_nullrol_csak_egyszer_engedi_a_hirdetes_idt():
    sql = MIGRACIO.read_text(encoding="utf-8")

    assert "old.hirdetes_id is not null" in sql
    assert "new.hirdetes_id is distinct from old.hirdetes_id" in sql
    assert "NULL-rol toltheto" in sql


def test_uj_kinyert_sor_proveniencia_nelkul_adatbazisban_is_tiltott():
    sql = MIGRACIO.read_text(encoding="utf-8")

    assert "if new.snapshot_id is null then" in sql
    assert "substring(" in sql
    assert "tg_op <> 'INSERT'" in sql


def test_actions_es_gyujtok_nem_tartalmaznak_gemini_kapcsolot():
    for relativ in (
        ".github/workflows/jooble_gyujto.yml",
        "scripts/jooble_gyujto.py",
        "scripts/eures_gyujto.py",
    ):
        tartalom = (GYOKER / relativ).read_text(encoding="utf-8").lower()
        assert "gemini" not in tartalom


@pytest.mark.parametrize(
    "allas",
    [
        {
            "cim": "Élő keresési találat",
            "ceg": "Teszt Kft.",
            "snippet": "Rövid, nem auditált találat.",
            "link": "https://example.test/live",
            "forras_tipus": "portal",
        },
        {
            "cim": "Mock találat",
            "ceg": "Mock Kft.",
            "snippet": "Tesztadat provenance nélkül.",
            "link": "https://example.test/mock",
            "forras_tipus": "egyeb",
        },
    ],
)
def test_provenance_nelkuli_elo_es_mock_allas_nem_ir_adatbazist(
    monkeypatch,
    allas,
):
    from utils import adatbazis

    def tiltott_kliens():
        pytest.fail("Provenance nélküli találatnál DB-kliens sem kérhető.")

    monkeypatch.setattr(adatbazis, "kliens", tiltott_kliens)

    assert adatbazis.gyujtes_mentese(
        {"szakma": "teszt szakma"},
        [allas],
    ) == 0


def test_nem_elemezheto_allas_listazhato_de_nem_pontozhato(monkeypatch):
    from agents import karrier_ugynok

    modellhivasok = []

    def tiltott_modell(*args, **kwargs):
        modellhivasok.append((args, kwargs))
        raise AssertionError("Nem elemezhető állás nem kerülhet modellhez.")

    monkeypatch.setattr(karrier_ugynok, "gpt", tiltott_modell)
    allas = {
        "cim": "Listázható találat",
        "ceg": "Teszt Kft.",
        "snippet": "Rövid kivonat.",
        "link": "https://example.test/listazhato",
        "elemzesre_alkalmas": False,
    }

    lista = karrier_ugynok.allasok_rangsorolasa(
        "Jóváhagyott CV",
        [allas],
        {"szakma": "teszt szakma"},
    )
    diagnozis = karrier_ugynok.ats_diagnozis(
        "Jóváhagyott CV",
        [allas],
        {"szakma": "teszt szakma"},
    )

    assert len(lista) == 1
    assert lista[0]["elemzesre_alkalmas"] is False
    assert lista[0]["ats_elerheto"] is False
    assert lista[0]["szemelyre_szabott"] is False
    assert lista[0]["rangsorolt"] is False
    assert "illeszkedes" not in lista[0]
    assert diagnozis["ats_elerheto"] is False
    assert diagnozis["illeszkedes_szazalek"] is None
    assert modellhivasok == []


def _run_alap_mockok(monkeypatch, karrier_ugynok):
    monkeypatch.setattr(
        karrier_ugynok,
        "szakma_felismeres",
        lambda *_: {
            "szakma": "bolti eladó",
            "ajanlott_cegek": [],
            "szakma_kategoria": "kereskedelem",
            "portfilio_ajanlott": False,
        },
    )
    monkeypatch.setattr(karrier_ugynok, "kepzes_ajanlat", lambda *_: [])
    monkeypatch.setattr(
        karrier_ugynok,
        "gpt",
        lambda *_args, **_kwargs: pytest.fail(
            "Nem validált állásnál nincs személyre szabott modellhívás."
        ),
    )


def test_tesztmod_run_nem_ad_ures_allaslistat(monkeypatch):
    from agents import karrier_ugynok

    _run_alap_mockok(monkeypatch, karrier_ugynok)
    monkeypatch.setattr(karrier_ugynok, "TESZT_MOD", True)

    eredmeny = karrier_ugynok.run(
        cv_szoveg="Jóváhagyott CV",
        szakma_megadva="bolti eladó",
    )

    assert eredmeny["allasok"]
    assert all(
        allas["elemzesre_alkalmas"] is False
        for allas in eredmeny["allasok"]
    )
    assert all("illeszkedes" not in allas for allas in eredmeny["allasok"])
    assert eredmeny["diagnozis"]["ats_elerheto"] is False


class _KeresesiValasz:
    def json(self):
        return {
            "organic_results": [
                {"link": "https://example.test/allasok"}
            ]
        }


def test_elo_run_nem_ad_ures_allaslistat_es_nem_hiv_geminit(
    monkeypatch,
):
    from agents import karrier_ugynok

    _run_alap_mockok(monkeypatch, karrier_ugynok)
    monkeypatch.setattr(karrier_ugynok, "TESZT_MOD", False)
    monkeypatch.setattr(
        karrier_ugynok,
        "friss_hirdetesek",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        karrier_ugynok.requests,
        "get",
        lambda *_args, **_kwargs: _KeresesiValasz(),
    )
    gemini_hivasok = []

    def tiltott_post(url, *args, **kwargs):
        if "generativelanguage.googleapis.com" in str(url):
            gemini_hivasok.append((url, args, kwargs))
        raise AssertionError("Az interaktív állásfolyam nem POST-olhat modellhez.")

    monkeypatch.setattr(karrier_ugynok.requests, "post", tiltott_post)
    monkeypatch.setattr(
        karrier_ugynok,
        "oldal_letoltes",
        lambda *_: {
            "szoveg": "Teszt karrieroldal",
            "linkek": ["https://example.test/allas/1"],
        },
    )
    monkeypatch.setattr(
        karrier_ugynok,
        "allasok_kinyerese_oldalbol",
        lambda *_: [
            {
                "cim": "Élő raktáros állás",
                "ceg": "Teszt Kft.",
                "snippet": "Rövid, nem auditált élő találat.",
                "link": "https://example.test/allas/1",
                "datum": "2026-07-28",
                "helyszin": "Budapest",
            }
        ],
    )

    eredmeny = karrier_ugynok.run(
        cv_szoveg="Jóváhagyott CV",
        szakma_megadva="bolti eladó",
    )

    assert eredmeny["allasok"]
    assert eredmeny["allasok"][0]["elemzesre_alkalmas"] is False
    assert "illeszkedes" not in eredmeny["allasok"][0]
    assert gemini_hivasok == []


def test_minosegi_kereses_megmutatja_a_nem_elemezheto_talalatot(
    monkeypatch,
):
    from agents import karrier_ugynok

    nem_elemezheto = {
        "cim": "Élő, listázható állás",
        "ceg": "Teszt Kft.",
        "snippet": "Rövid kivonat.",
        "link": "https://example.test/lista/1",
        "elemzesre_alkalmas": False,
        "adatbazisbol": False,
    }
    monkeypatch.setattr(
        karrier_ugynok,
        "friss_hirdetesek",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        karrier_ugynok,
        "allasok_keresese",
        lambda *_args, **_kwargs: [nem_elemezheto],
    )
    monkeypatch.setattr(karrier_ugynok, "kereslet_korkep", lambda: [])

    eredmeny = karrier_ugynok.allasok_minosegi_kereses(
        "Jóváhagyott CV",
        {
            "szakma": "teszt szakma",
            "utos_kulcsszavak": ["Python"],
            "ajanlott_cegek": [],
        },
    )

    assert len(eredmeny["allasok"]) == 1
    assert eredmeny["allasok"][0]["elemzesre_alkalmas"] is False
    assert eredmeny["allasok"][0]["szemelyre_szabott"] is False
    assert "illeszkedes" not in eredmeny["allasok"][0]


def test_run_forrasaban_nincs_passziv_gemini_adatmentes():
    from agents import karrier_ugynok

    forras = inspect.getsource(karrier_ugynok.run)

    assert "keszsegek_kinyerese" not in forras
    assert "gyujtes_mentese" not in forras
