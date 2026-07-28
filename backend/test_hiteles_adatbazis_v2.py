from pathlib import Path

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
