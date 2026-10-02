from __future__ import annotations

import pytest

from app.retrieval.context import (
    GroundedContextItemV1,
    GroundedRetrievalContextV1,
)
from app.retrieval.prompt_contract import (
    build_grounded_answer_prompt,
)


def _grounded_context() -> GroundedRetrievalContextV1:
    item = GroundedContextItemV1(
        document_id="tehran.museum",
        title="Tehran Museum Guide",
        score=0.91,
        text="Tehran has several major museums.",
    )

    return GroundedRetrievalContextV1(
        query="Tehran museums",
        items=(item,),
        rendered_text=(
            "[document_id=tehran.museum score=0.9100]\n"
            "Tehran Museum Guide\n"
            "Tehran has several major museums."
        ),
    )


def test_prompt_with_grounding_marks_has_grounding_true():
    prompt = build_grounded_answer_prompt(
        question="What museums should I visit?",
        context=_grounded_context(),
    )

    assert prompt.has_grounding is True


def test_prompt_preserves_source_document_ids():
    prompt = build_grounded_answer_prompt(
        question="What museums should I visit?",
        context=_grounded_context(),
    )

    assert prompt.source_document_ids == (
        "tehran.museum",
    )


def test_prompt_contains_grounded_context():
    context = _grounded_context()

    prompt = build_grounded_answer_prompt(
        question="What museums should I visit?",
        context=context,
    )

    assert context.rendered_text in prompt.user_prompt


def test_prompt_requires_document_id_citations():
    prompt = build_grounded_answer_prompt(
        question="What museums should I visit?",
        context=_grounded_context(),
    )

    assert "document_id" in prompt.system_prompt
    assert "square brackets" in prompt.system_prompt


def test_prompt_prohibits_unsupported_facts():
    prompt = build_grounded_answer_prompt(
        question="What museums should I visit?",
        context=_grounded_context(),
    )

    assert "Do not invent facts" in prompt.system_prompt


def test_empty_context_marks_has_grounding_false():
    context = GroundedRetrievalContextV1(
        query="Unknown destination",
    )

    prompt = build_grounded_answer_prompt(
        question="Tell me about this place.",
        context=context,
    )

    assert prompt.has_grounding is False
    assert prompt.source_document_ids == ()


def test_empty_context_requires_insufficient_sources_response():
    context = GroundedRetrievalContextV1(
        query="Unknown destination",
    )

    prompt = build_grounded_answer_prompt(
        question="Tell me about this place.",
        context=context,
    )

    assert "insufficient" in prompt.user_prompt


@pytest.mark.parametrize(
    "question",
    [
        "",
        " ",
        "\n\t",
    ],
)
def test_empty_question_is_rejected(
    question: str,
):
    context = GroundedRetrievalContextV1(
        query="Tehran"
    )

    with pytest.raises(
        ValueError,
        match="question must not be empty",
    ):
        build_grounded_answer_prompt(
            question=question,
            context=context,
        )


def test_question_is_trimmed():
    prompt = build_grounded_answer_prompt(
        question="  What museums should I visit?  ",
        context=_grounded_context(),
    )

    assert (
        "Question:\nWhat museums should I visit?"
        in prompt.user_prompt
    )


def test_prompt_does_not_claim_external_search():
    prompt = build_grounded_answer_prompt(
        question="What museums should I visit?",
        context=_grounded_context(),
    )

    assert "searched external sources" in prompt.system_prompt