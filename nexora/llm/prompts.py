"""Prompt templates for the two model-driven stages of the Nexora pipeline.

Keeping prompts out of the service and UI code makes them easy to audit and
tweak without touching program logic.
"""

from __future__ import annotations

from nexora.models import ContextPiece

ALLOWED_ENTITY_TYPES = (
    "PERSON",
    "ORGANIZATION",
    "PRODUCT",
    "TECHNOLOGY",
    "LOCATION",
    "EVENT",
    "CONCEPT",
)

_EXTRACTION_TEMPLATE = """\
You convert short source documents into a structured knowledge graph.

Read the document below and identify the meaningful entities it mentions,
then describe how those entities relate to one another.

Respond with JSON only, following this exact shape:
{{
  "entities": [
    {{"name": "Entity name exactly as written", "type": "PERSON|ORGANIZATION|PRODUCT|TECHNOLOGY|LOCATION|EVENT|CONCEPT", "summary": "one sentence describing what this entity is"}}
  ],
  "relations": [
    {{"source": "Entity name", "target": "Entity name", "type": "SHORT_UPPERCASE_PREDICATE", "context": "one sentence explaining why these two are connected"}}
  ]
}}

Rules:
- Entity names must match the spelling used in the document.
- A relation may only reference entity names that appear in the "entities" array.
- Prefer a handful of precise relations over many weak ones.
- Do not invent entities that are not present in the document.
- Return valid JSON with no surrounding prose or code fences.

Document:
{content}
"""

_ANSWER_TEMPLATE = """\
You are a research analyst answering a question from a knowledge graph.

The numbered entries below are the only facts retrieved for this question.
Every entry names an entity, its type, a short summary, the source document
it came from, and the graph route that reached it.

Answer the QUESTION using these entries. Requirements:
- For any claim you make, add the bracket reference of the entries it relies on, e.g. [1] or [2][3].
- Base every statement on the entries. If the entries do not contain enough
  information to answer confidently, say so instead of guessing.
- Never invent people, organisations, numbers or products.
- Keep the answer concise and clearly structured.

Entries:
{entries}

QUESTION: {question}
"""


def build_extraction_prompt(content: str) -> str:
    """Assemble the entity/relation extraction prompt for a document."""
    return _EXTRACTION_TEMPLATE.format(content=content)


def format_context_piece(index: int, piece: ContextPiece) -> str:
    """Render a single retrieved entity as a numbered prompt entry line."""
    parts = [f"[{index}] Entity: {piece.name} ({piece.kind or 'UNKNOWN'})"]
    if piece.summary:
        parts.append(f"Summary: {piece.summary}")
    if piece.document:
        parts.append(f"Source: {piece.document}")
    if piece.route:
        parts.append(f"Graph route: {'; '.join(piece.route)}")
    return " | ".join(parts)


def build_answer_prompt(question: str, pieces: list[ContextPiece]) -> str:
    """Assemble the grounded-answering prompt."""
    entries = "\n".join(
        format_context_piece(index, piece)
        for index, piece in enumerate(pieces, start=1)
    )
    return _ANSWER_TEMPLATE.format(entries=entries, question=question)
