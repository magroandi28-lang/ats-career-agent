"""A modellkapu hálózati hívás nélküli szerződéstesztjei."""

import pytest

from backend.career_state_machine import CareerAction, CareerIntent
from backend.flow_contract import FlowDecision
from backend.model_gateway import (
    ModelCall,
    ModelGateway,
    ModelGatewayError,
    _openai_strict_schema,
)


class FakeAdapter:
    def __init__(self, result):
        self.result = result
        self.last_call: ModelCall | None = None

    def structured_response(self, call: ModelCall):
        self.last_call = call
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_gateway_strukturalt_valaszt_ad_vissza():
    expected = FlowDecision(
        intent=CareerIntent.CV_FRISSITES,
        response_message="A meglévő CV-det szeretnéd frissíteni.",
        proposed_action=CareerAction.CEL_MEGEROSITESE,
        confidence=0.95,
    )
    adapter = FakeAdapter(expected)

    result = ModelGateway(adapter).structured_response(
        task_type="flow_routing",
        system_instructions="teszt",
        input_data={"uzenet": "frissítsd a CV-met"},
        output_schema=FlowDecision,
        timeout_seconds=3,
    )

    assert result == expected
    assert adapter.last_call.task_type == "flow_routing"
    assert adapter.last_call.timeout_seconds == 3


def test_gateway_egyseges_hibara_forditja_az_adapter_hibat():
    adapter = FakeAdapter(ValueError("hibás JSON"))

    with pytest.raises(ModelGatewayError):
        ModelGateway(adapter).structured_response(
            task_type="flow_routing",
            system_instructions="teszt",
            input_data={},
            output_schema=FlowDecision,
        )


def test_flow_schema_nem_fogad_ismeretlen_szandekot():
    with pytest.raises(ValueError):
        FlowDecision(
            intent="talalj_ot_allast",
            response_message="Indítom.",
        )


def test_openai_strict_schema_minden_mezot_kotelezoen_felsorol():
    schema = _openai_strict_schema(FlowDecision.model_json_schema())

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
