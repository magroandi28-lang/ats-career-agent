"""Szolgáltatófüggetlen, strukturált LLM-hívási kapu."""

from dataclasses import dataclass
import json
from typing import Protocol, TypeVar

from pydantic import BaseModel
import requests

from backend.settings import get_settings
from backend.usage_log import (
    Hasznalat,
    gemini_hasznalat,
    openai_hasznalat,
    rogzit,
)


OutputModel = TypeVar("OutputModel", bound=BaseModel)


class ModelGatewayError(RuntimeError):
    """Biztonságosan megjeleníthető modellkapu-hiba."""


@dataclass(frozen=True)
class ModelCall:
    task_type: str
    system_instructions: str
    input_data: dict
    output_schema: type[OutputModel]
    timeout_seconds: int


class ModelAdapter(Protocol):
    def structured_response(self, call: ModelCall) -> OutputModel: ...


# Az adapter a hívás után ide teszi a token-adatot, és a kapu innen olvassa
# ki a naplózáshoz. Azért mellékcsatornán és nem visszatérési értékben, hogy
# a hívók és a tesztek adapterei változtatás nélkül működjenek tovább.
# Adapterpéldány hívásonként készül, tehát nem keveredhet két hívás adata.
_HASZNALAT_MEZO = "utolso_hasznalat"


def _response_output_text(payload: dict) -> str:
    if payload.get("output_text"):
        return payload["output_text"]
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("text"):
                return content["text"]
    raise ModelGatewayError("A modell nem adott feldolgozható választ.")


def _openai_strict_schema(schema: dict) -> dict:
    """Az OpenAI strict JSON Schema minden objektummezőt kötelezőként vár."""
    schema = dict(schema)
    schema.pop("default", None)
    if schema.get("type") == "object" or "properties" in schema:
        properties = {
            key: _openai_strict_schema(value)
            for key, value in schema.get("properties", {}).items()
        }
        schema["properties"] = properties
        schema["required"] = list(properties)
        schema["additionalProperties"] = False
    if "items" in schema:
        schema["items"] = _openai_strict_schema(schema["items"])
    if "$defs" in schema:
        schema["$defs"] = {
            key: _openai_strict_schema(value)
            for key, value in schema["$defs"].items()
        }
    for keyword in ("anyOf", "oneOf", "allOf"):
        if keyword in schema:
            schema[keyword] = [
                _openai_strict_schema(value) for value in schema[keyword]
            ]
    return schema


class OpenAIAdapter:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.utolso_hasznalat: Hasznalat | None = None

    def structured_response(self, call: ModelCall) -> OutputModel:
        schema = _openai_strict_schema(call.output_schema.model_json_schema())
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "instructions": call.system_instructions,
                "input": json.dumps(call.input_data, ensure_ascii=False),
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": call.output_schema.__name__,
                        "strict": True,
                        "schema": schema,
                    }
                },
            },
            timeout=call.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        # A token-adatot a sémavalidáció ELŐTT vesszük ki: a hívás akkor is
        # pénzbe került, ha a válasz utána érvénytelennek bizonyul.
        self.utolso_hasznalat = openai_hasznalat(payload)
        return call.output_schema.model_validate_json(
            _response_output_text(payload)
        )


class GeminiAdapter:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.utolso_hasznalat: Hasznalat | None = None

    def structured_response(self, call: ModelCall) -> OutputModel:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        response = requests.post(
            url,
            params={"key": self.api_key},
            json={
                "systemInstruction": {
                    "parts": [{"text": call.system_instructions}]
                },
                "contents": [{"parts": [{
                    "text": json.dumps(call.input_data, ensure_ascii=False)
                }]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseJsonSchema": call.output_schema.model_json_schema(),
                },
            },
            timeout=call.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        self.utolso_hasznalat = gemini_hasznalat(payload)
        try:
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelGatewayError(
                "A modell nem adott feldolgozható választ."
            ) from exc
        return call.output_schema.model_validate_json(text)


class ModelGateway:
    def __init__(self, adapter: ModelAdapter | None = None):
        self._adapter = adapter

    def _configured_adapter(self, task_type: str) -> ModelAdapter:
        settings = get_settings()
        model = settings.model_for_task(task_type)
        provider = settings.provider_for_task(task_type)
        if provider == "gemini":
            if not settings.gemini_api_key:
                raise ModelGatewayError("A Gemini nincs konfigurálva.")
            return GeminiAdapter(settings.gemini_api_key, model)
        if provider == "openai":
            if not settings.openai_api_key:
                raise ModelGatewayError("Az OpenAI nincs konfigurálva.")
            return OpenAIAdapter(settings.openai_api_key, model)
        raise ModelGatewayError("Ismeretlen AI-szolgáltató.")

    def structured_response(
        self,
        *,
        task_type: str,
        system_instructions: str,
        input_data: dict,
        output_schema: type[OutputModel],
        timeout_seconds: int | None = None,
        user_id: str | None = None,
    ) -> OutputModel:
        settings = get_settings()
        provider = settings.provider_for_task(task_type)
        call = ModelCall(
            task_type=task_type,
            system_instructions=system_instructions,
            input_data=input_data,
            output_schema=output_schema,
            timeout_seconds=timeout_seconds or settings.ai_timeout_seconds,
        )
        adapter = self._adapter or self._configured_adapter(task_type)
        try:
            return adapter.structured_response(call)
        except (requests.RequestException, ValueError, ModelGatewayError) as exc:
            raise ModelGatewayError("A modellhívás nem sikerült.") from exc
        finally:
            # A naplózás a `finally`-ben van: a sikertelen hívás is pénzbe
            # kerülhetett, és épp a hibás futásokat fontos látni a keretnél.
            self._naplozas(adapter, task_type, provider, user_id)

    @staticmethod
    def _naplozas(
        adapter: ModelAdapter,
        task_type: str,
        szolgaltato: str,
        user_id: str | None,
    ) -> None:
        hasznalat = getattr(adapter, _HASZNALAT_MEZO, None)
        # Nincs token-adat: a hívás el sem jutott a szolgáltatóig, vagy a
        # tesztek behelyettesített adaptere fut. Nincs mit naplózni.
        if hasznalat is None:
            return
        rogzit(
            feladat=task_type,
            szolgaltato=szolgaltato,
            modell=getattr(adapter, "model", "ismeretlen"),
            hasznalat=hasznalat,
            user_id=user_id,
        )
