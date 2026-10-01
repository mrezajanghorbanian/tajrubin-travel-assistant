from __future__ import annotations

from typing import Any, Mapping

import httpx

from app.providers.text_generation import (
    TextGenerationRequestV1,
    TextGenerationResponseV1,
    TextGenerationUsageV1,
)


class OpenAICompatibleProviderError(RuntimeError):
    """Raised when an OpenAI-compatible provider cannot return a valid response."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class OpenAICompatibleTextGenerationProvider:
    """Text-generation adapter for OpenAI-compatible chat-completions APIs."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        normalized_base_url = base_url.strip().rstrip("/")

        if not normalized_base_url:
            raise ValueError("base_url must not be empty.")

        if not model.strip():
            raise ValueError("model must not be empty.")

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero.")

        self._base_url = normalized_base_url
        self._model = model.strip()
        self._api_key = api_key
        self._owns_client = client is None

        self._client = client or httpx.Client(
            timeout=timeout_seconds,
        )

    def generate(
        self,
        request: TextGenerationRequestV1,
    ) -> TextGenerationResponseV1:
        messages: list[dict[str, str]] = []

        if request.system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": request.system_prompt,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": request.prompt,
            }
        )

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        headers = {
            "Content-Type": "application/json",
        }

        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            response = self._client.post(
                f"{self._base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise OpenAICompatibleProviderError(
                "timeout",
                "OpenAI-compatible provider request timed out.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise OpenAICompatibleProviderError(
                "http_error",
                f"OpenAI-compatible provider returned HTTP {exc.response.status_code}.",
            ) from exc
        except httpx.HTTPError as exc:
            raise OpenAICompatibleProviderError(
                "transport_error",
                "OpenAI-compatible provider request failed.",
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise OpenAICompatibleProviderError(
                "invalid_json",
                "OpenAI-compatible provider returned invalid JSON.",
            ) from exc

        return self._parse_response(data)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "OpenAICompatibleTextGenerationProvider":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _parse_response(
        self,
        data: Mapping[str, Any],
    ) -> TextGenerationResponseV1:
        try:
            choices = data["choices"]
            first_choice = choices[0]
            message = first_choice["message"]
            text = message["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenAICompatibleProviderError(
                "invalid_response",
                "OpenAI-compatible provider response shape is invalid.",
            ) from exc

        if not isinstance(text, str) or not text.strip():
            raise OpenAICompatibleProviderError(
                "empty_response",
                "OpenAI-compatible provider returned empty text.",
            )

        usage_data = data.get("usage") or {}

        if not isinstance(usage_data, Mapping):
            usage_data = {}

        usage = TextGenerationUsageV1(
            prompt_tokens=_optional_non_negative_int(
                usage_data.get("prompt_tokens")
            ),
            completion_tokens=_optional_non_negative_int(
                usage_data.get("completion_tokens")
            ),
            total_tokens=_optional_non_negative_int(
                usage_data.get("total_tokens")
            ),
        )

        model_name = data.get("model")

        if model_name is not None and not isinstance(model_name, str):
            model_name = str(model_name)

        return TextGenerationResponseV1(
            text=text.strip(),
            model_name=model_name or self._model,
            usage=usage,
        )


def _optional_non_negative_int(
    value: Any,
) -> int | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, int) and value >= 0:
        return value

    return None


__all__ = [
    "OpenAICompatibleProviderError",
    "OpenAICompatibleTextGenerationProvider",
]
