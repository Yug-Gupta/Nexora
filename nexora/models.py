"""Domain records shared across the storage, retrieval and UI layers.

These frozen dataclasses are the vocabulary of the whole pipeline: what the
extractor produces, what the repository persists, what retrieval collects and
what the UI renders.  Keeping them in one module prevents drift between
layers.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

_ID_NAMESPACE = "ent"


def _clean_token(value: str) -> str:
    """Collapse whitespace and trim stray punctuation for matching purposes."""
    return re.sub(r"\s+", " ", value.strip())


def entity_identifier(name: str) -> str:
    """Deterministic graph key derived from a normalised entity name.

    Two documents that mention the same entity in a slightly different
    capitalisation resolve to the same key, which lets the graph merge them
    into a single node across sources.
    """
    normalised = _clean_token(name).casefold()
    digest = hashlib.sha256(normalised.encode("utf-8")).hexdigest()[:16]
    return f"{_ID_NAMESPACE}:{digest}"


@dataclass(frozen=True)
class Entity:
    """A single typed concept discovered inside a source document."""

    name: str
    kind: str
    summary: str = ""
    source_label: str = ""
    excerpt: str = ""


@dataclass(frozen=True)
class Relation:
    """A directed link between two entities with an explanation."""

    subject: str
    object: str
    predicate: str
    rationale: str = ""
    source_label: str = ""


@dataclass(frozen=True)
class ContextPiece:
    """A retrieved entity together with the route that reached it."""

    name: str
    kind: str
    summary: str
    document: str
    excerpt: str = ""
    route: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProvenanceRecord:
    """A single citation tying a generated statement to its source."""

    index: int
    entity: str
    document: str
    quote: str
    route: tuple[str, ...] = ()


@dataclass(frozen=True)
class QueryAnswer:
    """The final answer plus the evidence and audit trail behind it."""

    text: str
    references: tuple[ProvenanceRecord, ...] = ()
    audit: tuple[str, ...] = ()


@dataclass(frozen=True)
class IngestReport:
    """What happened while turning one document into graph records."""

    source_label: str
    entity_count: int
    relation_count: int
    dropped_relations: int = 0
    entities: tuple[Entity, ...] = ()
    relations: tuple[Relation, ...] = ()


@dataclass(frozen=True)
class StoreOverview:
    """Live size of the knowledge graph and the documents it came from."""

    node_count: int = 0
    edge_count: int = 0
    document_count: int = 0
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class HealthProbe:
    """Result of a single infrastructure connectivity check."""

    component: str
    available: bool
    message: str = ""
    extra: tuple[str, ...] = field(default_factory=tuple)


def truncate(text: str, limit: int = 280) -> str:
    """Clip long excerpts to ``limit`` characters and append an ellipsis."""
    if text is None:
        return ""
    compact = re.sub(r"\s+", " ", text.strip())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


__all__ = [
    "ContextPiece",
    "Entity",
    "HealthProbe",
    "IngestReport",
    "ProvenanceRecord",
    "QueryAnswer",
    "Relation",
    "StoreOverview",
    "entity_identifier",
    "truncate",
]
