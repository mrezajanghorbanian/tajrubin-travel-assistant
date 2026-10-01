from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.providers.openai_compatible import (
    OpenAICompatibleTextGenerationProvider,
)
from app.providers.runtime_config import (
    LocalProviderRuntimeConfigV1,
    build_local_text_generation_provider,
)


def test_runtime_config_uses_local_defaults():
    config = LocalProviderRuntimeConfigV1()

    assert config.base_url == "http://127.0.0.1:1234"
    assert config.model == "qwen3.5-4b"
    assert config.api_key is None
    assert config.timeout_seconds == 600.0


def test_runtime_config_accepts_custom_values():
    config = LocalProviderRuntimeConfigV1(
        base_url="http://localhost:9999",
        model="custom-local-model",
        api_key="local-key",
        timeout_seconds=120.0,
    )

    assert config.base_url == "http://localhost:9999"
    assert config.model == "custom-local-model"
    assert config.api_key == "local-key"
    assert config.timeout_seconds == 120.0


def test_runtime_config_rejects_empty_base_url():
    with pytest.raises(ValidationError):
        LocalProviderRuntimeConfigV1(
            base_url=""
        )


def test_runtime_config_rejects_empty_model():
    with pytest.raises(ValidationError):
        LocalProviderRuntimeConfigV1(
            model=""
        )


@pytest.mark.parametrize(
    "timeout_seconds",
    [0, -1, 3601],
)
def test_runtime_config_rejects_invalid_timeout(timeout_seconds):
    with pytest.raises(ValidationError):
        LocalProviderRuntimeConfigV1(
            timeout_seconds=timeout_seconds
        )


def test_runtime_config_is_frozen():
    config = LocalProviderRuntimeConfigV1()

    with pytest.raises(ValidationError):
        config.model = "changed"


def test_builder_returns_openai_compatible_provider():
    config = LocalProviderRuntimeConfigV1()

    provider = build_local_text_generation_provider(config)

    assert isinstance(
        provider,
        OpenAICompatibleTextGenerationProvider,
    )

    provider.close()


def test_builder_preserves_runtime_values():
    config = LocalProviderRuntimeConfigV1(
        base_url="http://127.0.0.1:4321/",
        model="test-model",
        api_key="abc",
        timeout_seconds=90.0,
    )

    provider = build_local_text_generation_provider(config)

    assert provider._base_url == "http://127.0.0.1:4321"
    assert provider._model == "test-model"
    assert provider._api_key == "abc"

    provider.close()