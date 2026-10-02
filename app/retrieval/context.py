from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.retrieval.contract import RetrievalResultV1


class GroundedContextItemV1(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    document_id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    score: float = Field(ge=0.0, le=1.0)
    text: str = Field(min_length=1, max_length=4000)


class GroundedRetrievalContextV1(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    query: str = Field(min_length=1, max_length=500)
    items: tuple[GroundedContextItemV1, ...] = ()
    rendered_text: str = Field(default="", max_length=12000)


def build_grounded_retrieval_context(
    result: RetrievalResultV1,
    *,
    max_items: int = 5,
    max_item_chars: int = 1200,
    max_total_chars: int = 6000,
) -> GroundedRetrievalContextV1:
    if max_items < 1:
        raise ValueError("max_items must be at least 1")

    if max_item_chars < 100:
        raise ValueError("max_item_chars must be at least 100")

    if max_total_chars < max_item_chars:
        raise ValueError(
            "max_total_chars must be greater than or equal to max_item_chars"
        )

    items: list[GroundedContextItemV1] = []
    rendered_parts: list[str] = []
    used_chars = 0

    for hit in result.hits[:max_items]:
        document = hit.document

        source_text = _compose_document_text(
            title=document.title,
            summary=document.summary,
            content=document.content,
        )

        separator_size = 2 if rendered_parts else 0
        remaining = max_total_chars - used_chars - separator_size

        header = (
            f"[document_id={document.document_id} score={hit.score:.4f}]\n"
        )

        if remaining <= len(header):
            break

        item_budget = min(
            max_item_chars,
            remaining - len(header),
        )

        item_text = _truncate(
            source_text,
            item_budget,
        )

        if not item_text.strip():
            break

        rendered = f"{header}{item_text}"

        items.append(
            GroundedContextItemV1(
                document_id=document.document_id,
                title=document.title,
                score=hit.score,
                text=item_text,
            )
        )

        rendered_parts.append(rendered)
        used_chars += separator_size + len(rendered)

    rendered_text = "\n\n".join(rendered_parts)

    if len(rendered_text) > max_total_chars:
        rendered_text = _truncate(
            rendered_text,
            max_total_chars,
        )

    return GroundedRetrievalContextV1(
        query=result.query.text,
        items=tuple(items),
        rendered_text=rendered_text,
    )


def _compose_document_text(
    *,
    title: str,
    summary: str,
    content: str,
) -> str:
    parts = [
        title.strip(),
        summary.strip(),
        content.strip(),
    ]

    return "\n".join(
        part
        for part in parts
        if part
    )


def _truncate(
    value: str,
    max_chars: int,
) -> str:
    if len(value) <= max_chars:
        return value

    return value[:max_chars].rstrip()


__all__ = [
    "GroundedContextItemV1",
    "GroundedRetrievalContextV1",
    "build_grounded_retrieval_context",
]
