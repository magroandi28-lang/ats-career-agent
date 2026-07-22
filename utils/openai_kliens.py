# -*- coding: utf-8 -*-
"""OPENAI KAPCSOLAT — a korábbi Claude-hívások kiváltására.

Egyetlen közös hívó-függvény, hogy mind a ~10 helyen ugyanúgy, egységesen
fusson (kevesebb az esély elgépelésre, mint 10 külön requests.post-nál).

Modellek (2026-os OpenAI felállás):
  GYORS    = gpt-5.6-luna   — kinyerés/osztályozás/JSON (korábbi claude-haiku-4-5 helyett)
  MINOSEGI = gpt-5.6-terra  — fogalmazás: CV, motivációs levél, portfólió-szöveg
             (korábbi claude-sonnet-4-5 helyett)

Fontos különbség a Claude-hoz képest: ezek "reasoning" modellek, a
temperature paraméter NEM állítható (csak az alapértelmezett 1 engedélyezett) —
ezért determinisztikusabb, kinyerő feladatoknál a reasoning_effort="low"
paramétert használjuk temperature=0 helyett.
"""

import os

import requests

_URL = "https://api.openai.com/v1/chat/completions"

GYORS = "gpt-5.6-luna"
MINOSEGI = "gpt-5.6-terra"


def gpt(messages: list, model: str = GYORS, max_tokens: int = 1200,
        reasoning_effort: str = None) -> str:
    """Egy hívás az OpenAI chat/completions végpontjára.

    Visszaadja a válasz szövegét (strip-elve). Hiba esetén feldobja a
    kivételt — a hívó fél ugyanúgy try/except-eli, mint eddig a Claude-nál."""
    kulcs = os.getenv("OPENAI_API_KEY", "")
    adat = {"model": model, "messages": messages, "max_completion_tokens": max_tokens}
    if reasoning_effort:
        adat["reasoning_effort"] = reasoning_effort
    r = requests.post(_URL, headers={"Authorization": f"Bearer {kulcs}"},
                       json=adat, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()
