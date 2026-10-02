from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
)

from app.providers.openai_compatible import (
    OpenAICompatibleTextGenerationProvider,
)


class LocalProviderRuntimeConfigV1(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    base_url: str = Field(
        default="http://127.0.0.1:1234",
        min_length=1,
        max_length=2048,
    )

    model: str = Field(
        default="qwen3.5-4b",
        min_length=1,
        max_length=300,
    )

    api_key: SecretStr | None = None

    timeout_seconds: float = Field(
        default=600.0,
        gt=0,
        le=3600,
    )

    @field_validator("base_url")
    @classmethod
    def validate_local_base_url(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlparse(normalized)

        if parsed.scheme not in {"http", "https"}:
            raise ValueError(
                "base_url must use http or https."
            )

        hostname = parsed.hostname

        if hostname is None:
            raise ValueError(
                "base_url must include a hostname."
            )

        if hostname == "localhost":
            return normalized

        try:
            address = ip_address(hostname)
        except ValueError as exc:
            raise ValueError(
                "local provider base_url must use a loopback host."
            ) from exc

        if not address.is_loopback:
            raise ValueError(
                "local provider base_url must use a loopback host."
            )

        return normalized


def build_local_text_generation_provider(
    config: LocalProviderRuntimeConfigV1,
) -> OpenAICompatibleTextGenerationProvider:
    api_key = (
        config.api_key.get_secret_value()
        if config.api_key is not None
        else None
    )

    return OpenAICompatibleTextGenerationProvider(
        base_url=config.base_url,
        model=config.model,
        api_key=api_key,
        timeout_seconds=config.timeout_seconds,
    )


__all__ = [
    "LocalProviderRuntimeConfigV1",
    "build_local_text_generation_provider",
]