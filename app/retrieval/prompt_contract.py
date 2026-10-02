from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.retrieval.context import GroundedRetrievalContextV1


class GroundedAnswerPromptV1(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    system_prompt: str = Field(min_length=1, max_length=6000)
    user_prompt: str = Field(min_length=1, max_length=14000)
    source_document_ids: tuple[str, ...] = ()
    has_grounding: bool


def build_grounded_answer_prompt(
    *,
    question: str,
    context: GroundedRetrievalContextV1,
) -> GroundedAnswerPromptV1:
    normalized_question = question.strip()

    if not normalized_question:
        raise ValueError("question must not be empty")

    system_prompt = (
        "You are a grounded travel assistant. "
        "Answer using only the supplied grounded context. "
        "Do not invent facts that are not supported by the context. "
        "When you use factual information from a source, cite its "
        "document_id in square brackets, for example [tehran.museum]. "
        "If the context does not contain enough information to answer, "
        "say that the available grounded sources are insufficient. "
        "Do not claim that you searched external sources unless such "
        "sources are explicitly present in the supplied context."
    )

    source_document_ids = tuple(
        item.document_id
        for item in context.items
    )

    if context.items:
        user_prompt = (
            f"Question:\n{normalized_question}\n\n"
            "Grounded context:\n"
            f"{context.rendered_text}\n\n"
            "Instructions:\n"
            "- Answer the question directly.\n"
            "- Use only the grounded context above for factual claims.\n"
            "- Cite supporting document IDs in square brackets.\n"
            "- Do not cite document IDs that are not present above."
        )
        has_grounding = True
    else:
        user_prompt = (
            f"Question:\n{normalized_question}\n\n"
            "Grounded context:\n"
            "[none]\n\n"
            "Instructions:\n"
            "- State that the available grounded sources are insufficient.\n"
            "- Do not invent an answer.\n"
            "- Do not fabricate citations."
        )
        has_grounding = False

    return GroundedAnswerPromptV1(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        source_document_ids=source_document_ids,
        has_grounding=has_grounding,
    )


__all__ = [
    "GroundedAnswerPromptV1",
    "build_grounded_answer_prompt",
]