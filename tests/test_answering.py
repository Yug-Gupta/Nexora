"""Tests for grounded answering and citation verification."""

from __future__ import annotations

from nexora.models import ContextPiece
from nexora.pipeline.answering import (
    _collect_references,
    _expand_cited_indices,
    synthesise_answer,
)


def _piece(name, excerpt="quote", document="doc"):
    return ContextPiece(
        name=name,
        kind="PERSON",
        summary="summary",
        document=document,
        excerpt=excerpt,
        route=("A --[x]-- B",),
    )


PIECES = [_piece("Alice", document="d1"), _piece("Bob", document="d2")]


def test_expand_cited_indices_handles_groups_and_duplicates():
    text = "Answer with [1] and [2], or combined [1, 2] and [1,3] again."
    assert _expand_cited_indices(text) == [1, 2, 3]


def test_collect_references_only_resolves_real_entries():
    answer = "Alice did X [1]. Bob did Y [2]. Unknown [99]."
    refs = _collect_references(answer, PIECES)
    assert [r.index for r in refs] == [1, 2]
    assert refs[0].entity == "Alice"
    assert refs[0].document == "d1"
    assert refs[0].quote == "quote"


def test_collect_references_ignores_zero():
    assert _collect_references("text [0]", PIECES) == ()


def test_collect_references_sorted_by_index():
    answer = "Y [2] came before X [1]."
    refs = _collect_references(answer, PIECES)
    assert [r.index for r in refs] == [1, 2]


class _AnswerGateway:
    def __init__(self, reply: str):
        self.reply = reply

    def complete(self, prompt, model_name=None, *, expect_json=False):
        return self.reply


def test_synthesise_answer_returns_text_and_references():
    gateway = _AnswerGateway(
        "Alice founded Aster [1]. Bob leads product [2]. Out of scope [99]."
    )
    text, refs = synthesise_answer("who did what?", PIECES, gateway)
    assert "[1]" in text
    assert len(refs) == 2


def test_synthesise_answer_without_citations_returns_empty_references():
    gateway = _AnswerGateway("I do not have enough information to answer.")
    text, refs = synthesise_answer("unknown?", PIECES, gateway)
    assert refs == ()
    assert "enough information" in text
