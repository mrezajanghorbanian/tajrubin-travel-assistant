from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.providers.text_generation import (
    TextGenerationRequestV1,
    TextGenerationResponseV1,
    TextGenerationUsageV1,
)


def test_request_accepts_valid_values():
    request = TextGenerationRequestV1(
        prompt="Plan a 3-day trip to Tehran.",
        system_prompt="You are a travel assistant.",
        temperature=0.3,
        max_tokens=800,
    )

    assert request.prompt == "Plan a 3-day trip to Tehran."
    assert request.system_prompt == "You are a travel assistant."
    assert request.temperature == 0.3
    assert request.max_tokens == 800


def test_request_uses_safe_defaults():
    request = TextGenerationRequestV1(
        prompt="Tell me about Shiraz."
    )

    assert request.system_prompt is None
    assert request.temperature == 0.2
    assert request.max_tokens == 1024


@pytest.mark.parametrize(
    "temperature",
    [-0.1, 2.1],
)
def test_request_rejects_invalid_temperature(temperature):
    with pytest.raises(ValidationError):
        TextGenerationRequestV1(
            prompt="Test",
            temperature=temperature,
        )


@pytest.mark.parametrize(
    "max_tokens",
    [0, 32769],
)
def test_request_rejects_invalid_max_tokens(max_tokens):
    with pytest.raises(ValidationError):
        TextGenerationRequestV1(
            prompt="Test",
            max_tokens=max_tokens,
        )


def test_request_rejects_empty_prompt():
    with pytest.raises(ValidationError):
        TextGenerationRequestV1(
            prompt=""
        )


def test_usage_accepts_partial_usage_data():
    usage = TextGenerationUsageV1(
        prompt_tokens=100,
        completion_tokens=50,
    )

    assert usage.prompt_tokens == 100
    assert usage.completion_tokens == 50
    assert usage.total_tokens is None


def test_usage_rejects_negative_tokens():
    with pytest.raises(ValidationError):
        TextGenerationUsageV1(
            total_tokens=-1
        )


def test_response_accepts_valid_response():
    response = TextGenerationResponseV1(
        text="Tehran is a strong starting point for an Iran trip.",
        model_name="local-model",
        usage=TextGenerationUsageV1(
            total_tokens=120
        ),
    )

    assert response.text.startswith("Tehran")
    assert response.model_name == "local-model"
    assert response.usage.total_tokens == 120


def test_response_rejects_empty_text():
    with pytest.raises(ValidationError):
        TextGenerationResponseV1(
            text=""
        )


def test_models_are_frozen():
    request = TextGenerationRequestV1(
        prompt="Test"
    )

    with pytest.raises(ValidationError):
        request.prompt = "Changed"