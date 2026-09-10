"""Compose a grounded answer and verify the citations inside it.

The answer stage hands the retrieved context to Gemini as numbered
entries and asks it to cite them inline as ``[1]``, ``[2]`` and so on.  After
generation every bracket citation found in the text is resolved back to a
context entry; citations that do not correspond to a real entry are simply
not shown, so the UI never fabricates sources.
"""

from __future__ import annotations

import logging
import re

from nexora.llm.gateway import InferenceGateway
from nexora.llm.prompts import build_answer_prompt
from nexora.models import ContextPiece, ProvenanceRecord

logger = logging.getLogger(__name__)

# Matches a single "[3]" and also comma/space separated groups such as
# "[1, 2]" or "[1,2,3]" which some models produce instead of "[1][2]".
_CITATION_PATTERN = re.compile(r"\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\]")


def _expand_cited_indices(answer_text: str) -> list[int]:
    """Return every valid, de-duplicated citation index in appearance order."""
    indices: list[int] = []
    for group in _CITATION_PATTERN.findall(answer_text):
        for token in group.split(","):
            raw = token.strip()
            if not raw:
                continue
            try:
                value = int(raw)
            except ValueError:
                continue
            if value >= 1 and value not in indices:
                indices.append(value)
    return indices


def _collect_references(
    answer_text: str,
    pieces: list[ContextPiece],
) -> tuple[ProvenanceRecord, ...]:
    """Resolve every bracket citation in the text back to a context piece."""
    references: list[ProvenanceRecord] = []
    for index in _expand_cited_indices(answer_text):
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
    """Generate a response grounded on ``pieces`` and verify its citations.

    Raises :class:`~nexora.errors.InferenceError` when the model call itself
    fails; an answer that simply omits citations is returned as-is (the UI
    explains that the model qualified or generalised).
    """
    prompt = build_answer_prompt(question, pieces)
    answer_text = gateway.complete(prompt, model_name=model_name, expect_json=False)
    references = _collect_references(answer_text, pieces)
    logger.info(
        "Answer generated with %d verified citation(s)",
        len(references),
    )
    return answer_text, references
