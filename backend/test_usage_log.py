"""A költségnapló tesztjei -- hálózati hívás és adatbázis nélkül.

A szolgáltatók válaszai elmentett fixture-ök: így a lánc ezerszer
ellenőrizhető anélkül, hogy egyetlen fillért is fogyasztana.
"""

from decimal import Decimal

import pytest

from backend import usage_log
from backend.usage_log import (
    Hasznalat,
    gemini_hasznalat,
    koltseg_usd,
    openai_hasznalat,
    rogzit,
)


# Egy valódi OpenAI `responses` válasz váza, csak a naplózáshoz kellő
# mezőkkel.
OPENAI_RESPONSES_VALASZ = {
    "output_text": '{"intent": "cv_frissites"}',
    "usage": {"input_tokens": 1200, "output_tokens": 800},
}

# A régi `chat/completions` végpont ugyanezt más néven adja vissza.
OPENAI_CHAT_VALASZ = {
    "choices": [{"message": {"content": "kész CV"}}],
    "usage": {"prompt_tokens": 1200, "completion_tokens": 800},
}

GEMINI_VALASZ = {
    "candidates": [{"content": {"parts": [{"text": "{}"}]}}],
    "usageMetadata": {"promptTokenCount": 500, "candidatesTokenCount": 250},
}


def test_openai_mindket_vegpont_nevkeszletet_erti():
    assert openai_hasznalat(OPENAI_RESPONSES_VALASZ) == Hasznalat(1200, 800)
    assert openai_hasznalat(OPENAI_CHAT_VALASZ) == Hasznalat(1200, 800)


def test_gemini_token_kinyerese():
    assert gemini_hasznalat(GEMINI_VALASZ) == Hasznalat(500, 250)


def test_hianyzo_usage_blokk_nem_hasal_el():
    assert openai_hasznalat({}) == Hasznalat(0, 0)
    assert gemini_hasznalat({}) == Hasznalat(0, 0)


def test_koltseg_a_dragabb_modellel():
    # gpt-5.6-terra: 2,50 USD/millió bemenet, 15,00 USD/millió kimenet.
    # 1200 * 2,50/1e6 + 800 * 15,00/1e6 = 0,003 + 0,012 = 0,015
    assert koltseg_usd("gpt-5.6-terra", Hasznalat(1200, 800)) == Decimal("0.015000")


def test_ingyenes_kereten_nincs_koltseg():
    """A Gemini ingyenes keretén a hívás nem kerül pénzbe -- nulla, nem becslés."""
    assert koltseg_usd(
        "gemini-2.5-flash", Hasznalat(500, 250), szolgaltato="gemini"
    ) == Decimal(0)


def test_gemini_fizetos_kereten_szamol(monkeypatch):
    """Ha egyszer fizetősre váltasz, ugyanaz a napló már valós összeget mutat."""
    monkeypatch.setenv("GEMINI_FIZETOS", "1")
    # gemini-2.5-flash: 0,30 és 2,50 USD/millió.
    # 500 * 0,30/1e6 + 250 * 2,50/1e6 = 0,00015 + 0,000625 = 0,000775
    assert koltseg_usd(
        "gemini-2.5-flash", Hasznalat(500, 250), szolgaltato="gemini"
    ) == Decimal("0.000775")


def test_ingyenes_kereten_is_rogzulnek_a_tokenek(monkeypatch):
    """A keret fogyása enélkül láthatatlan maradna."""
    beszurt = {}

    class FakeTabla:
        def insert(self, sor):
            beszurt.update(sor)
            return self

        def execute(self):
            return None

    class FakeSema:
        def table(self, nev):
            return FakeTabla()

    class FakeKliens:
        def schema(self, nev):
            return FakeSema()

    monkeypatch.setattr(usage_log, "kliens", lambda: FakeKliens())

    rogzit(
        feladat="keszsegkinyeres_gyujteskor",
        szolgaltato="gemini",
        modell="gemini-2.5-flash",
        hasznalat=Hasznalat(500, 250),
    )

    assert beszurt["bemeneti_tokenek"] == 500
    assert beszurt["kimeneti_tokenek"] == 250
    assert beszurt["koltseg_usd"] == "0"


def test_ismeretlen_modell_nulla_koltseg_de_nem_hiba():
    """Nem tippelünk árat: a kitalált szám hamis biztonságérzetet adna."""
    assert koltseg_usd("valami-uj-modell", Hasznalat(1000, 1000)) == Decimal(0)


def test_rogzit_a_szamolt_koltseggel_ir(monkeypatch):
    beszurt = {}

    class FakeTabla:
        def insert(self, sor):
            beszurt.update(sor)
            return self

        def execute(self):
            return None

    class FakeSema:
        def table(self, nev):
            beszurt["_tabla"] = nev
            return FakeTabla()

    class FakeKliens:
        def schema(self, nev):
            beszurt["_sema"] = nev
            return FakeSema()

    monkeypatch.setattr(usage_log, "kliens", lambda: FakeKliens())

    rogzit(
        feladat="cv_atiras",
        szolgaltato="openai",
        modell="gpt-5.6-terra",
        hasznalat=Hasznalat(1200, 800),
        user_id="u-1",
    )

    assert beszurt["_sema"] == "private"
    assert beszurt["_tabla"] == "model_usage"
    assert beszurt["feladat"] == "cv_atiras"
    assert beszurt["bemeneti_tokenek"] == 1200
    assert beszurt["koltseg_usd"] == "0.015000"
    assert beszurt["sikeres"] is True


def test_rogzit_nem_dobja_tovabb_az_adatbazis_hibat(monkeypatch):
    """A naplózás kísérőtevékenység: nem akaszthatja meg a felhasználó kérését."""

    def robban():
        raise RuntimeError("nincs adatbázis")

    monkeypatch.setattr(usage_log, "kliens", robban)

    rogzit(
        feladat="cv_atiras",
        szolgaltato="openai",
        modell="gpt-5.6-terra",
        hasznalat=Hasznalat(10, 10),
    )


def test_naplo_nem_tarol_szoveget(monkeypatch):
    """A napló mennyiséget mér, nem tartalmat -- ez GDPR-szempontból is számít."""
    beszurt = {}

    class FakeTabla:
        def insert(self, sor):
            beszurt.update(sor)
            return self

        def execute(self):
            return None

    class FakeSema:
        def table(self, nev):
            return FakeTabla()

    class FakeKliens:
        def schema(self, nev):
            return FakeSema()

    monkeypatch.setattr(usage_log, "kliens", lambda: FakeKliens())

    rogzit(
        feladat="cv_atiras",
        szolgaltato="openai",
        modell="gpt-5.6-terra",
        hasznalat=Hasznalat(1, 1),
    )

    tiltott = {"prompt", "valasz", "messages", "content", "cv_szoveg"}
    assert tiltott.isdisjoint(beszurt)


@pytest.mark.parametrize("modell", sorted(usage_log.ARAK))
def test_minden_arhoz_ket_szam_tartozik(modell):
    be, ki = usage_log.ARAK[modell]
    assert be >= 0 and ki >= 0
