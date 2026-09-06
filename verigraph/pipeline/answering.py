"""Compose a grounded answer and verify the citations inside it."""

from __future__ import annotations

import logging
import re

from verigraph.llm.gateway import InferenceGateway
from verigraph.llm.prompts import build_answer_prompt
from verigraph.models import ContextPiece, ProvenanceRecord

logger = logging.getLogger(__name__)

_CITATION_PATTERN = re.compile(r"\[(\d{1,3})\]")


def _collect_references(
    answer_text: str,
    pieces: list[ContextPiece],
) -> tuple[ProvenanceRecord, ...]:
    """Resolve every bracket citation in the text back to a context piece."""
    references: list[ProvenanceRecord] = []
    for raw in _CITATION_PATTERN.findall(answer_text):
        index = int(raw)
        if not 1 <= index <= len(pieces):
            continue
        piece = pieces[index - 1]
        if any(existing.index == index for existing in references):
            continue
        references.append(
            ProvenanceRecord(
                index=index,
                entity=piece.name,
                document=piece.document,
                quote=piece.excerpt,
                route=piece.route,
            )
        )
    references.sort(key=lambda item: item.index)
    return tuple(references)


def synthesise_answer(
    question: str,
    pieces: list[ContextPiece],
    gateway: InferenceGateway,
    model_name: str | None = None,
) -> tuple[str, tuple[ProvenanceRecord, ...]]:
    """Generate a response grounded on ``pieces`` and verify its citations."""
    prompt = build_answer_prompt(question, pieces)
    answer_text = gateway.complete(prompt, model_name=model_name, expect_json=False)
    references = _collect_references(answer_text, pieces)
    logger.info(
        "Answer generated with %d verified citation(s)",
        len(references),
    )
    return answer_text, references
