from __future__ import annotations

import pytest
from pydantic import ValidationError, SecretStr

from app.providers.runtime_config import (
    LocalProviderRuntimeConfigV1,
    build_local_text_generation_provider,
)


def test_runtime_config_accepts_loopback_ipv4():
    config = LocalProviderRuntimeConfigV1(
        base_url="http://127.0.0.1:1234"
    )

    assert config.base_url == "http://127.0.0.1:1234"


def test_runtime_config_accepts_localhost():
    config = LocalProviderRuntimeConfigV1(
        base_url="http://localhost:1234/"
    )

    assert config.base_url == "http://localhost:1234"


def test_runtime_config_accepts_loopback_ipv6():
    config = LocalProviderRuntimeConfigV1(
        base_url="http://[::1]:1234"
    )

    assert config.base_url == "http://[::1]:1234"


@pytest.mark.parametrize(
    "base_url",
    [
        "http://8.8.8.8:1234",
        "http://192.168.1.10:1234",
        "http://10.0.0.5:1234",
        "http://172.16.0.5:1234",
        "http://169.254.169.254",
        "https://example.com",
        "ftp://127.0.0.1:1234",
    ],
)
def test_runtime_config_rejects_non_loopback_or_invalid_urls(base_url):
    with pytest.raises(ValidationError):
        LocalProviderRuntimeConfigV1(
            base_url=base_url
        )


def test_api_key_uses_secret_type():
    config = LocalProviderRuntimeConfigV1(
        api_key="super-secret-value"  # pragma: allowlist secret
    )

    assert isinstance(config.api_key, SecretStr)
    assert config.api_key.get_secret_value() == "super-secret-value"


def test_api_key_is_redacted_in_repr():
    config = LocalProviderRuntimeConfigV1(
        api_key="super-secret-value"  # pragma: allowlist secret
    )

    rendered = repr(config)

    assert "super-secret-value" not in rendered
    assert "**********" in rendered


def test_builder_unwraps_secret_only_for_provider_runtime():
    config = LocalProviderRuntimeConfigV1(
        api_key="runtime-secret"  # pragma: allowlist secret  # pragma: allowlist secret
    )

    provider = build_local_text_generation_provider(config)

    assert provider._api_key == "runtime-secret"  # pragma: allowlist secret

    provider.close()