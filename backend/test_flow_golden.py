# -*- coding: utf-8 -*-
"""A golden set ingyenes rétege: modellhívás nélkül futó garanciák.

Nem azt méri, hogy a modell mit válaszol -- azt a
`scripts/flow_golden_futtato.py` méri, valódi hívásokkal. Ez itt azt
bizonyítja, hogy AKÁRMIT is javasol a modell, az orchestrator nem tudja
végrehajtani a tiltott műveletet, mert az állapotgép nem engedi.

Ez a különbségtétel fontos: a prompt bármikor romolhat, a kapunak akkor
is tartania kell.
"""

import pytest

from backend.career_state_machine import allowed_actions, next_state
from backend.golden_flow import ESETEK, GOLDEN_VERZIO
from backend.workflow_actions import vegrehajthato


def test_van_golden_eset():
    assert ESETEK, "A golden set nem lehet üres."
    assert GOLDEN_VERZIO


def test_az_azonositok_egyediek():
    azonositok = [eset.azonosito for eset in ESETEK]
    assert len(azonositok) == len(set(azonositok))


@pytest.mark.parametrize("eset", ESETEK, ids=lambda e: e.azonosito)
def test_a_tiltott_akciot_az_allapotgep_sem_engedi(eset):
    """A tiltás nem a prompt jóindulatán múlik.

    Ha egy tiltott művelet mégis végrehajtható lenne az adott állapotból,
    akkor a védelem csak a modell jólneveltségén áll -- az pedig nem
    védelem. Ilyenkor vagy az állapotgépet kell szigorítani, vagy az
    esetet átgondolni.
    """
    for akcio in eset.tiltott_akciok:
        cel = next_state(eset.allapot, akcio)
        assert cel is None, (
            f"{eset.azonosito}: a(z) {akcio.value} művelet végrehajtható a(z) "
            f"{eset.allapot.value} állapotból, pedig tiltottnak jelöltük. "
            f"Indok: {eset.indok}"
        )


@pytest.mark.parametrize("eset", ESETEK, ids=lambda e: e.azonosito)
def test_a_tiltott_akcio_nincs_a_felkinalt_listaban(eset):
    """A felület sem kínálhatja fel, amit a golden set tilt."""
    engedett = allowed_actions(eset.allapot)
    for akcio in eset.tiltott_akciok:
        assert akcio not in engedett, (
            f"{eset.azonosito}: a(z) {akcio.value} szerepel az engedélyezett "
            f"listában {eset.allapot.value} állapotban."
        )


@pytest.mark.parametrize("eset", ESETEK, ids=lambda e: e.azonosito)
def test_a_bekototten_muveletek_kapun_belul_maradnak(eset):
    """Amit ma végre tudunk hajtani, arra is vonatkozik a tiltás."""
    for akcio in eset.tiltott_akciok:
        if vegrehajthato(akcio):
            assert next_state(eset.allapot, akcio) is None
