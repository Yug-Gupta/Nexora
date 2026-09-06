"""Multi-hop retrieval: find starting points, then expand around them."""

from __future__ import annotations

import logging
import re

from verigraph.config import Settings
from verigraph.db.repository import KnowledgeBase
from verigraph.errors import ContextError
from verigraph.models import ContextPiece

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "at",
    "for", "with", "about", "what", "which", "who", "whom", "whose",
    "when", "where", "why", "how", "does", "did", "is", "are", "was",
    "were", "do", "be", "it", "its", "this", "that", "their", "there",
    "from", "by", "as", "not", "no", "have", "has", "had", "can", "could",
}

_WORD_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_'./+&*-]{1,}")


def derive_terms(question: str) -> list[str]:
    """Split a question into useful, case-folded search keywords."""
    tokens = _WORD_PATTERN.findall(question)
    terms: list[str] = []
    for token in tokens:
        lowered = token.casefold()
        if len(lowered) < 3 or lowered in _STOPWORDS:
            continue
        terms.append(lowered)
    return terms


def collect_context(
    question: str,
    store: KnowledgeBase,
    settings: Settings,
) -> tuple[list[ContextPiece], list[str], list[str]]:
    """Return evidence pieces plus a human-readable audit of the search.

    Retrieval happens in two phases:

    1. keyword match picks a handful of *seed* entities;
    2. for each seed, the graph is walked ``retrieval_depth`` hops and every
       newly reached entity becomes a candidate context piece.
    """
    audit: list[str] = []
    terms = derive_terms(question)
    if not terms:
        raise ContextError(
            "No searchable terms could be extracted from that question. "
            "Please rephrase it with more concrete keywords."
        )

    audit.append(f"Search terms: {', '.join(terms)}")
    seeds = store.locate_entry_points(terms=terms, limit=settings.entry_limit)
    if not seeds:
        raise ContextError(
            "Nothing in the knowledge graph matched this question. "
            "Ingest related documents first, or rephrase with terms that "
            "appear in the graph."
        )
    audit.append(f"{len(seeds)} matching entities found to start from")

    chosen = seeds[:3]
    audit.append(
        "Starting points: " + ", ".join(seed["name"] for seed in chosen)
    )

    pieces: list[ContextPiece] = []
    seen_names: set[str] = set()

    def add_piece(piece: ContextPiece) -> None:
        if piece.name.casefold() in seen_names:
            return
        if len(pieces) >= settings.context_cap:
            return
        seen_names.add(piece.name.casefold())
        pieces.append(piece)

    for seed in chosen:
        add_piece(
            ContextPiece(
                name=seed["name"],
                kind=seed["kind"],
                summary=seed["summary"],
                document=seed["doc_label"],
                excerpt=seed["excerpt"],
            )
        )

    for seed in chosen:
        neighbours = store.grow_neighbourhood(
            seed_id=seed["entity_id"],
            depth=settings.retrieval_depth,
            window=settings.context_cap,
        )
        audit.append(f"{len(neighbours)} related nodes reached from '{seed['name']}'")
        for row in neighbours:
            add_piece(
                ContextPiece(
                    name=row["name"],
                    kind=row["kind"],
                    summary=row["summary"],
                    document=row["doc_label"],
                    excerpt=row["excerpt"],
                    route=tuple(row["route"]),
                )
            )
            if len(pieces) >= settings.context_cap:
                break

    if not pieces:
        raise ContextError(
            "The graph matched entities but no connected context could be "
            "assembled. Try ingesting more documents about this topic."
        )
    audit.append(f"Assembled {len(pieces)} context entries for the answer")
    logger.info("Retrieval produced %d context pieces", len(pieces))
    return pieces, [seed["name"] for seed in chosen], audit
