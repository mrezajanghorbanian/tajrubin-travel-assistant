from __future__ import annotations

import httpx
import pytest

from app.providers.openai_compatible import (
    OpenAICompatibleProviderError,
    OpenAICompatibleTextGenerationProvider,
)
from app.providers.text_generation import (
    TextGenerationRequestV1,
)


def _client(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


def test_provider_sends_openai_compatible_chat_request():
    captured = {}

    def handler(request: httpx.Request):
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["json"] = request.read().decode("utf-8")

        return httpx.Response(
            200,
            json={
                "model": "local-qwen",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Tehran is a useful starting point."
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 8,
                    "total_tokens": 20,
                },
            },
        )

    client = _client(handler)

    provider = OpenAICompatibleTextGenerationProvider(
        base_url="http://127.0.0.1:1234",
        model="local-qwen",
        api_key="test-key",  # pragma: allowlist secret
        client=client,
    )

    response = provider.generate(
        TextGenerationRequestV1(
            prompt="Tell me about Tehran.",
            system_prompt="You are a travel assistant.",
            temperature=0.3,
            max_tokens=500,
        )
    )

    assert captured["method"] == "POST"
    assert captured["url"] == "http://127.0.0.1:1234/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-key"

    assert response.text == "Tehran is a useful starting point."
    assert response.model_name == "local-qwen"
    assert response.usage.prompt_tokens == 12
    assert response.usage.completion_tokens == 8
    assert response.usage.total_tokens == 20


def test_provider_does_not_require_api_key_for_local_endpoint():
    def handler(request: httpx.Request):
        assert "Authorization" not in request.headers

        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "Local response."
                        }
                    }
                ]
            },
        )

    provider = OpenAICompatibleTextGenerationProvider(
        base_url="http://localhost:1234/",
        model="local-model",
        client=_client(handler),
    )

    response = provider.generate(
        TextGenerationRequestV1(
            prompt="Test local model."
        )
    )

    assert response.text == "Local response."
    assert response.model_name == "local-model"


def test_provider_rejects_empty_base_url():
    with pytest.raises(ValueError):
        OpenAICompatibleTextGenerationProvider(
            base_url="   ",
            model="local-model",
        )


def test_provider_rejects_empty_model():
    with pytest.raises(ValueError):
        OpenAICompatibleTextGenerationProvider(
            base_url="http://localhost:1234",
            model="   ",
        )


def test_provider_rejects_non_positive_timeout():
    with pytest.raises(ValueError):
        OpenAICompatibleTextGenerationProvider(
            base_url="http://localhost:1234",
            model="local-model",
            timeout_seconds=0,
        )


def test_provider_maps_http_status_error():
    def handler(request: httpx.Request):
        return httpx.Response(
            500,
            request=request,
            json={"error": "failure"},
        )

    provider = OpenAICompatibleTextGenerationProvider(
        base_url="http://localhost:1234",
        model="local-model",
        client=_client(handler),
    )

    with pytest.raises(OpenAICompatibleProviderError) as exc:
        provider.generate(
            TextGenerationRequestV1(
                prompt="Test"
            )
        )

    assert exc.value.code == "http_error"


def test_provider_maps_transport_error():
    def handler(request: httpx.Request):
        raise httpx.ConnectError(
            "connection failed",
            request=request,
        )

    provider = OpenAICompatibleTextGenerationProvider(
        base_url="http://localhost:1234",
        model="local-model",
        client=_client(handler),
    )

    with pytest.raises(OpenAICompatibleProviderError) as exc:
        provider.generate(
            TextGenerationRequestV1(
                prompt="Test"
            )
        )

    assert exc.value.code == "transport_error"


def test_provider_rejects_invalid_json():
    def handler(request: httpx.Request):
        return httpx.Response(
            200,
            request=request,
            content=b"not-json",
            headers={
                "Content-Type": "application/json",
            },
        )

    provider = OpenAICompatibleTextGenerationProvider(
        base_url="http://localhost:1234",
        model="local-model",
        client=_client(handler),
    )

    with pytest.raises(OpenAICompatibleProviderError) as exc:
        provider.generate(
            TextGenerationRequestV1(
                prompt="Test"
            )
        )

    assert exc.value.code == "invalid_json"


def test_provider_rejects_invalid_response_shape():
    def handler(request: httpx.Request):
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [],
            },
        )

    provider = OpenAICompatibleTextGenerationProvider(
        base_url="http://localhost:1234",
        model="local-model",
        client=_client(handler),
    )

    with pytest.raises(OpenAICompatibleProviderError) as exc:
        provider.generate(
            TextGenerationRequestV1(
                prompt="Test"
            )
        )

    assert exc.value.code == "invalid_response"


def test_provider_rejects_empty_response_text():
    def handler(request: httpx.Request):
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "   "
                        }
                    }
                ]
            },
        )

    provider = OpenAICompatibleTextGenerationProvider(
        base_url="http://localhost:1234",
        model="local-model",
        client=_client(handler),
    )

    with pytest.raises(OpenAICompatibleProviderError) as exc:
        provider.generate(
            TextGenerationRequestV1(
                prompt="Test"
            )
        )

    assert exc.value.code == "empty_response"


def test_provider_ignores_invalid_usage_values():
    def handler(request: httpx.Request):
        return httpx.Response(
            200,
            request=request,
            json={
                "model": "local-model",
                "choices": [
                    {
                        "message": {
                            "content": "Valid response."
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": -10,
                    "completion_tokens": "invalid",
                    "total_tokens": True,
                },
            },
        )

    provider = OpenAICompatibleTextGenerationProvider(
        base_url="http://localhost:1234",
        model="local-model",
        client=_client(handler),
    )

    response = provider.generate(
        TextGenerationRequestV1(
            prompt="Test"
        )
    )

    assert response.usage.prompt_tokens is None
    assert response.usage.completion_tokens is None
    assert response.usage.total_tokens is None


def test_provider_does_not_close_external_client():
    client = _client(
        lambda request: httpx.Response(
            200,
            request=request,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "OK"
                        }
                    }
                ]
            },
        )
    )

    provider = OpenAICompatibleTextGenerationProvider(
        base_url="http://localhost:1234",
        model="local-model",
        client=client,
    )

    provider.close()

    assert client.is_closed is False

    client.close()


def test_provider_closes_owned_client():
    provider = OpenAICompatibleTextGenerationProvider(
        base_url="http://localhost:1234",
        model="local-model",
    )

    provider.close()

    assert provider._client.is_closed is True
