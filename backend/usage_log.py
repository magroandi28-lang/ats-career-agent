"""Modellhívások költségnaplója.

Minden fizetős hívás ide kerül, hogy a keret állása az alkalmazásból
látszódjon, ne a szolgáltató fiókjából.

A napló szándékosan nem tárol prompt- vagy válaszszöveget: a mennyiséghez
és a költséghez van köze, nem a tartalomhoz.
"""

from dataclasses import dataclass
from decimal import Decimal
import logging

from utils.adatbazis import kliens


_LOG = logging.getLogger(__name__)


# Millió tokenre eső ár USD-ben: modell -> (bemenet, kimenet).
# Források: developers.openai.com/api/docs/pricing és
# ai.google.dev/gemini-api/docs/pricing -- ellenőrizve 2026-07-27.
#
# Az árak változnak. Ha a szolgáltató számlája eltér a naplótól, ITT kell
# javítani: ez az egyetlen hely, ahol ár szerepel a rendszerben.
ARAK: dict[str, tuple[Decimal, Decimal]] = {
    # A CV- és levélíráshoz használt minőségi modell -- ez a legdrágább út.
    "gpt-5.6-terra": (Decimal("2.50"), Decimal("15.00")),
    # Kinyerés, osztályozás, JSON.
    "gpt-5.6-luna": (Decimal("1.00"), Decimal("6.00")),
    "gemini-2.5-pro": (Decimal("1.25"), Decimal("10.00")),
    "gemini-2.5-flash": (Decimal("0.30"), Decimal("2.50")),
}

_MILLIO = Decimal(1_000_000)
_FILLER = Decimal("0.000001")


@dataclass(frozen=True)
class Hasznalat:
    """Egy modellhívás token-fogyasztása."""

    bemeneti_tokenek: int = 0
    kimeneti_tokenek: int = 0


def openai_hasznalat(payload: dict) -> Hasznalat:
    """Token-adat az OpenAI válaszából.

    Két végpontot is használunk: a `responses` `input_tokens`/`output_tokens`,
    a régi `chat/completions` `prompt_tokens`/`completion_tokens` néven adja
    vissza ugyanazt.
    """
    usage = payload.get("usage") or {}
    return Hasznalat(
        bemeneti_tokenek=int(
            usage.get("input_tokens") or usage.get("prompt_tokens") or 0
        ),
        kimeneti_tokenek=int(
            usage.get("output_tokens") or usage.get("completion_tokens") or 0
        ),
    )


def gemini_hasznalat(payload: dict) -> Hasznalat:
    """Token-adat a Gemini válaszából."""
    usage = payload.get("usageMetadata") or {}
    return Hasznalat(
        bemeneti_tokenek=int(usage.get("promptTokenCount") or 0),
        kimeneti_tokenek=int(usage.get("candidatesTokenCount") or 0),
    )


def koltseg_usd(modell: str, hasznalat: Hasznalat) -> Decimal:
    """A hívás becsült ára.

    Ismeretlen modellnél nulla: nem tippelünk. A tokenek ilyenkor is
    rögzülnek, tehát az ár utólag pótolható -- egy kitalált ár viszont
    hamis biztonságérzetet adna a keretedről.
    """
    arak = ARAK.get(modell)
    if arak is None:
        _LOG.warning(
            "Nincs ár a(z) %s modellhez, a költség 0-ként kerül a naplóba.",
            modell,
        )
        return Decimal(0)

    be_ar, ki_ar = arak
    teljes = (
        be_ar * hasznalat.bemeneti_tokenek + ki_ar * hasznalat.kimeneti_tokenek
    ) / _MILLIO
    return teljes.quantize(_FILLER)


def rogzit(
    *,
    feladat: str,
    szolgaltato: str,
    modell: str,
    hasznalat: Hasznalat,
    user_id: str | None = None,
    sikeres: bool = True,
    hiba: str | None = None,
) -> None:
    """Egy sor a költségnaplóba. Soha nem dob kivételt.

    A naplózás kísérőtevékenység: ha elhasal, attól a felhasználó kérése
    még teljesüljön. A hibát kiírjuk, de nem visszük tovább.
    """
    try:
        kliens().schema("private").table("model_usage").insert(
            {
                "user_id": user_id,
                "feladat": feladat,
                "szolgaltato": szolgaltato,
                "modell": modell,
                "bemeneti_tokenek": hasznalat.bemeneti_tokenek,
                "kimeneti_tokenek": hasznalat.kimeneti_tokenek,
                # Stringként megy: a numeric mezőbe a float kerekítési hibát
                # vinne, a Decimal pedig nem JSON-szerializálható.
                "koltseg_usd": str(koltseg_usd(modell, hasznalat)),
                "sikeres": sikeres,
                "hiba": str(hiba)[:200] if hiba else None,
            }
        ).execute()
    except Exception:
        _LOG.exception("A költségnapló írása nem sikerült.")
