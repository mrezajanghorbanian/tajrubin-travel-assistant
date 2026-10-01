from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.knowledge.contract import TravelKnowledgeDocumentV1


class TravelKnowledgeLoadError(ValueError):
    """Raised when a travel knowledge source document cannot be loaded."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def load_travel_knowledge_markdown(
    path: str | Path,
) -> TravelKnowledgeDocumentV1:
    source_path = Path(path)

    try:
        raw = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TravelKnowledgeLoadError(
            "source_unreadable",
            f"Unable to read knowledge source: {source_path}",
        ) from exc

    front_matter, body = _split_front_matter(raw)

    try:
        metadata = yaml.safe_load(front_matter)
    except yaml.YAMLError as exc:
        raise TravelKnowledgeLoadError(
            "invalid_front_matter",
            f"Invalid YAML front matter: {source_path}",
        ) from exc

    if not isinstance(metadata, dict):
        raise TravelKnowledgeLoadError(
            "invalid_front_matter",
            "Knowledge front matter must be a mapping.",
        )

    content = body.strip()

    if not content:
        raise TravelKnowledgeLoadError(
            "empty_content",
            "Knowledge document body must not be empty.",
        )

    payload: dict[str, Any] = dict(metadata)
    payload["content"] = content

    try:
        return TravelKnowledgeDocumentV1.model_validate(payload)
    except ValidationError as exc:
        raise TravelKnowledgeLoadError(
            "contract_rejected",
            "Knowledge document does not satisfy TravelKnowledgeDocumentV1.",
        ) from exc


def _split_front_matter(raw: str) -> tuple[str, str]:
    normalized = raw.lstrip("\ufeff")

    lines = normalized.splitlines()

    if not lines or lines[0].strip() != "---":
        raise TravelKnowledgeLoadError(
            "missing_front_matter",
            "Knowledge document must begin with YAML front matter.",
        )

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            front_matter = "\n".join(lines[1:index]).strip()
            body = "\n".join(lines[index + 1 :])

            if not front_matter:
                raise TravelKnowledgeLoadError(
                    "empty_front_matter",
                    "Knowledge front matter must not be empty.",
                )

            return front_matter, body

    raise TravelKnowledgeLoadError(
        "unterminated_front_matter",
        "Knowledge YAML front matter is not terminated.",
    )


__all__ = [
    "TravelKnowledgeLoadError",
    "load_travel_knowledge_markdown",
]