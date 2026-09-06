"""Multi-hop retrieval: find starting points, then expand around them.

A question is decomposed into search keywords, matching entities become
*seeds* (ranked by how many keywords they actually match), and the graph is
walked ``retrieval_depth`` hops from each seed.  Every entity reached along a
route becomes a context entry that also records the path used to reach it, so
downstream stages can show exactly how each piece of evidence was discovered.
"""

from __future__ import annotations

import logging
import re

from nexora.config import Settings
from nexora.db.repository import KnowledgeBase
from nexora.errors import ContextError
from nexora.models import ContextPiece

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "at",
    "for", "with", "about", "what", "which", "who", "whom", "whose",
    "when", "where", "why", "how", "does", "did", "is", "are", "was",
    "were", "do", "be", "it", "its", "this", "that", "their", "there",
    "from", "by", "as", "not", "no", "have", "has", "had", "can", "could",
}

_WORD_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_'./+&*-]{1,}")

_MAX_SEEDS_PER_QUERY = 3


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


def _match_score(seed: dict, terms: list[str]) -> int:
    """Count how many search terms appear across a seed's text fields."""
    haystack = " ".join(
        str(seed.get(key, "")) for key in ("name", "kind", "summary")
    ).casefold()
    return sum(1 for term in terms if term in haystack)


def _rank_seeds(seeds: list[dict], terms: list[str]) -> list[dict]:
    """Order candidate seeds by relevance, breaking ties alphabetically."""
    return sorted(
        seeds,
        key=lambda seed: (-_match_score(seed, terms), str(seed.get("name", "")).casefold()),
    )


def collect_context(
    question: str,
    store: KnowledgeBase,
    settings: Settings,
) -> tuple[list[ContextPiece], list[str], list[str]]:
    """Return evidence pieces plus a human-readable audit of the search.

    Retrieval happens in two phases:

    1. keyword match picks a handful of *seed* entities;
    2. for each seed, the graph is walked ``settings.retrieval_depth`` hops and
       every newly reached entity becomes a candidate context piece.
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

    ranked = _rank_seeds(seeds, terms)
    chosen = ranked[:_MAX_SEEDS_PER_QUERY]
    noun = "entity" if len(seeds) == 1 else "entities"
    audit.append(
        f"{len(seeds)} matching {noun} found; using the top {len(chosen)} as "
        "starting point(s)"
    )
    audit.append("Starting points: " + ", ".join(seed["name"] for seed in chosen))

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
        audit.append(f"{len(neighbours)} related node(s) reached from '{seed['name']}'")
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
