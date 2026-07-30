"""A tényhű CV-lánc és az adatbázisos szakmai háttér szerződéstesztjei."""

from types import SimpleNamespace

import pytest

from backend.cv_review_service import (
    CvAnalysis,
    CvFact,
    CvFactCheck,
    CvReviewError,
    CvWrittenDraft,
    create_improved_cv,
    database_context,
)
from backend.model_gateway import ModelGatewayError
from utils import adatbazis


FULL_ESCO_DESCRIPTION = (
    "A raktáros fogadja, ellenőrzi, nyilvántartja és a kijelölt helyre "
    "mozgatja az árukat; készletadatokat kezel és együttműködik a logisztikai "
    "folyamat résztvevőivel. Ez a teljes szakmai leírás nem jelöltbizonyíték."
)


class FakeGateway:
    def __init__(self, *, unsupported_anchor: bool = False):
        self.calls = []
        self.unsupported_anchor = unsupported_anchor

    def structured_response(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["task_type"] == "cv_analysis":
            return CvAnalysis(facts=[
                CvFact(
                    category="tapasztalat",
                    statement="Raktári nyilvántartást vezetett.",
                    source_quote="Raktári nyilvántartást vezettem.",
                )
            ])
        if kwargs["task_type"] == "cv_writing":
            return CvWrittenDraft(
                improved_cv="Raktári nyilvántartást vezettem."
            )
        checked_cv = "Raktári nyilvántartást vezettem."
        if self.unsupported_anchor:
            checked_cv += "\n99%-os eredményt értem el."
        return CvFactCheck(
            all_claims_supported=True,
            checked_cv=checked_cv,
            corrected_claims=[],
        )


def _market() -> dict:
    return {
        "target_role": "raktáros",
        "freshness": "2026-07-30T08:00:00+00:00",
        "active_ads": 20,
        "detailed_ads": 18,
        "requirements_confidence": "eros",
        "evidence_policy": "Az ESCO csak szakmai háttér, nem bizonyíték.",
        "esco_occupations": [{
            "name": "raktáros",
            "isco": "4321.1",
            "full_description": FULL_ESCO_DESCRIPTION,
            "required_skill_count": 12,
        }],
        "esco_core_skills": ["raktári nyilvántartás vezetése"],
        "advertised_requirements": [{
            "text": "készletnyilvántartás",
            "section": "elvaras",
            "sample_occurrences": 8,
        }],
    }


def test_database_context_teljes_esco_leirast_ad_at(monkeypatch):
    from backend import cv_review_service

    monkeypatch.setattr(cv_review_service, "szakma_id_nevbol", lambda _: 42)
    monkeypatch.setattr(
        cv_review_service,
        "szakma_csomag",
        lambda _: {
            "szakma": "raktáros",
            "frissesseg": "2026-07-30T08:00:00+00:00",
            "esco": [{
                "nev": "raktáros",
                "isco": "4321.1",
                "leiras": FULL_ESCO_DESCRIPTION,
                "kotelezo_keszseg": 12,
            }],
            "lefedettseg": {
                "allas": 20,
                "teteles": 18,
                "elvaras_bizalom": "eros",
            },
        },
    )
    monkeypatch.setattr(
        cv_review_service,
        "cv_illesztes",
        lambda *_args, **_kwargs: [{
            "keszseg": "raktári nyilvántartás vezetése",
            "kotelezo": True,
        }],
    )
    monkeypatch.setattr(
        cv_review_service,
        "szakma_hirdetes_mintak",
        lambda *_args, **_kwargs: [{
            "text": "készletnyilvántartás",
            "section": "elvaras",
            "sample_occurrences": 8,
        }],
    )

    context = database_context("raktáros")

    assert (
        context["esco_occupations"][0]["full_description"]
        == FULL_ESCO_DESCRIPTION
    )
    assert "nem bizonyít" in context["evidence_policy"]
    assert context["advertised_requirements"][0]["sample_occurrences"] == 8


def test_elemzo_es_iro_is_megkapja_a_teljes_esco_hatteret():
    gateway = FakeGateway()

    result = create_improved_cv(
        "Kiss Anna\nRaktári nyilvántartást vezettem.",
        "raktáros",
        gateway=gateway,
        market=_market(),
    )

    analyzer_input = gateway.calls[0]["input_data"]
    writer_input = gateway.calls[1]["input_data"]
    assert (
        analyzer_input["database_context"]["esco_occupations"][0][
            "full_description"
        ]
        == FULL_ESCO_DESCRIPTION
    )
    assert (
        writer_input["database_context"]["esco_occupations"][0][
            "full_description"
        ]
        == FULL_ESCO_DESCRIPTION
    )
    assert writer_input["verified_facts"] == [{
        "id": "F001",
        "category": "tapasztalat",
        "statement": "Raktári nyilvántartást vezetett.",
        "source_quote": "Raktári nyilvántartást vezettem.",
    }]
    assert result["database_basis"]["esco_occupations_considered"] == 1
    assert result["fact_check"]["status"] == "passed"


def test_esco_szoveg_nem_valhat_cv_tennye():
    class EscoHallucinatingGateway:
        def structured_response(self, **_kwargs):
            return CvAnalysis(facts=[
                CvFact(
                    category="készség",
                    statement="Készletadatokat kezel.",
                    source_quote="készletadatokat kezel",
                )
            ])

    with pytest.raises(CvReviewError, match="ellenőrizhető tényeket"):
        create_improved_cv(
            "Kiss Anna\nRaktárban dolgoztam.",
            "raktáros",
            gateway=EscoHallucinatingGateway(),
            market=_market(),
        )


def test_uj_szamot_a_determinisztikus_kapu_blokkol():
    with pytest.raises(CvReviewError, match="új számot"):
        create_improved_cv(
            "Kiss Anna\nRaktári nyilvántartást vezettem.",
            "raktáros",
            gateway=FakeGateway(unsupported_anchor=True),
            market=_market(),
        )


def test_modellhiba_biztonsagos_cv_hibava_alakul():
    class FailingGateway:
        def structured_response(self, **_kwargs):
            raise ModelGatewayError("belső részlet")

    with pytest.raises(CvReviewError, match="most nem sikerült"):
        create_improved_cv(
            "Kiss Anna\nRaktári nyilvántartást vezettem.",
            "raktáros",
            gateway=FailingGateway(),
            market=_market(),
        )


def test_hirdetesmintak_csak_tarolt_teteleket_csoportositanak(monkeypatch):
    rows = [
        {
            "szekcio": "elvaras",
            "szoveg": "Készletnyilvántartás",
            "normalizalt": "keszletnyilvantartas",
        },
        {
            "szekcio": "elvaras",
            "szoveg": "készletnyilvántartás",
            "normalizalt": "keszletnyilvantartas",
        },
        {
            "szekcio": "feladat",
            "szoveg": "Áruátvétel",
            "normalizalt": "aruatvetel",
        },
    ]

    class Query:
        def select(self, *_args):
            return self

        def eq(self, *_args):
            return self

        def in_(self, *_args):
            return self

        def limit(self, *_args):
            return self

        def execute(self):
            return SimpleNamespace(data=rows)

    class Db:
        def table(self, name):
            assert name == "hirdetes_tetel"
            return Query()

    monkeypatch.setattr(adatbazis, "kliens", lambda: Db())

    result = adatbazis.szakma_hirdetes_mintak(42, limit=2)

    assert result[0]["sample_occurrences"] == 2
    assert {item["section"] for item in result} == {"elvaras", "feladat"}
