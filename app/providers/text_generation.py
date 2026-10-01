from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )


class TextGenerationRequestV1(_StrictFrozenModel):
    """Provider-neutral text generation request."""

    prompt: str = Field(
        min_length=1,
        max_length=100_000,
    )

    system_prompt: str | None = Field(
        default=None,
        max_length=20_000,
    )

    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
    )

    max_tokens: int = Field(
        default=1024,
        ge=1,
        le=32_768,
    )


class TextGenerationUsageV1(_StrictFrozenModel):
    prompt_tokens: int | None = Field(
        default=None,
        ge=0,
    )

    completion_tokens: int | None = Field(
        default=None,
        ge=0,
    )

    total_tokens: int | None = Field(
        default=None,
        ge=0,
    )


class TextGenerationResponseV1(_StrictFrozenModel):
    """Provider-neutral response returned by a local or remote model."""

    text: str = Field(
        min_length=1,
        max_length=200_000,
    )

    model_name: str | None = Field(
        default=None,
        max_length=300,
    )

    usage: TextGenerationUsageV1 = Field(
        default_factory=TextGenerationUsageV1,
    )


class TextGenerationProvider(Protocol):
    """Minimal model-provider boundary for the travel assistant."""

    def generate(
        self,
        request: TextGenerationRequestV1,
    ) -> TextGenerationResponseV1:
        """Generate one response for a provider-neutral request."""


__all__ = [
    "TextGenerationProvider",
    "TextGenerationRequestV1",
    "TextGenerationResponseV1",
    "TextGenerationUsageV1",
]
