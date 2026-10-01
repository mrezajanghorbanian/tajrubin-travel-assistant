from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

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

    api_key: str | None = Field(
        default=None,
        max_length=1000,
    )

    timeout_seconds: float = Field(
        default=600.0,
        gt=0,
        le=3600,
    )


def build_local_text_generation_provider(
    config: LocalProviderRuntimeConfigV1,
) -> OpenAICompatibleTextGenerationProvider:
    return OpenAICompatibleTextGenerationProvider(
        base_url=config.base_url,
        model=config.model,
        api_key=config.api_key,
        timeout_seconds=config.timeout_seconds,
    )


__all__ = [
    "LocalProviderRuntimeConfigV1",
    "build_local_text_generation_provider",
]