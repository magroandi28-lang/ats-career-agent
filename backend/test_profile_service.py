"""Célfüggő profilkapu és bemeneti védelem tesztjei."""

import pytest

from backend.career_state_machine import CareerIntent
from backend.profile_service import (
    missing_profile_fields,
    profile_readiness,
    sanitize_profile_patch,
)


def test_allaskereseshez_celfuggo_minimum_kell():
    readiness = profile_readiness(
        CareerIntent.ALLAS_KERESES,
        {
            "confirmed_data": {
                "target_role": "automata tesztelő",
                "skills": ["Python", "Playwright"],
                "work_mode": "hibrid",
            }
        },
    )

    assert readiness["ready"] is True
    assert readiness["missing_fields"] == []


def test_cv_feltoltes_nem_tesz_allaskeresesre_keszze():
    missing = missing_profile_fields(
        CareerIntent.ALLAS_KERESES,
        {"cv_document_id": "cv-1"},
    )

    assert missing == ["target_role", "skills", "search_location"]


def test_tanacsadashoz_nem_kell_cv():
    readiness = profile_readiness(
        CareerIntent.TANACSADAS,
        {"confirmed_data": {"career_goal": "Megtalálni a következő irányt"}},
    )

    assert readiness["ready"] is True


def test_portfoliohoz_projekt_vagy_link_eleg():
    assert missing_profile_fields(
        CareerIntent.PORTFOLIO,
        {"project_links": ["https://github.com/pelda/projekt"]},
    ) == []


def test_ismeretlen_profilmezot_elutasit():
    with pytest.raises(ValueError):
        sanitize_profile_patch({"admin": "true"})


def test_lista_merete_es_tipusa_korlatozott():
    with pytest.raises(ValueError):
        sanitize_profile_patch({"skills": "Python"})
