"""Repository over the knowledge graph.

:class:`KnowledgeBase` is the only module that knows the schema laid out in
``statements``.  It converts domain records to and from graph rows and
exposes the exact read operations the retrieval pipeline needs.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

from neo4j.graph import Node, Relationship

from verigraph.db import connector, statements
from verigraph.errors import StorageError, translate_storage_failure
from verigraph.models import Entity, Relation, StoreOverview, entity_identifier

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """High-level read/write access to the entity graph."""

    def __init__(self, connection: connector.Neo4jConnector) -> None:
        self._connection = connection

    # -- lifecycle helpers ---------------------------------------------------

    @contextmanager
    def _session(self) -> Iterator[Any]:
        try:
            with self._connection.session() as session:
                yield session
        except StorageError:
            raise
        except Exception as exc:
            raise translate_storage_failure(exc) from exc

    # -- writes ---------------------------------------------------------------

    def save_entity(self, entity: Entity) -> None:
        """Insert or enrich a single entity node."""
        with self._session() as session:
            session.run(
                statements.UPSERT_ENTITY,
                entity_id=entity_identifier(entity.name),
                name=entity.name,
                kind=entity.kind,
                summary=entity.summary,
                doc_label=entity.source_label,
                excerpt=entity.excerpt,
            )
        logger.debug("Stored entity %r (%s)", entity.name, entity.kind)

    def save_relation(self, relation: Relation) -> bool:
        """Create a link if both endpoints exist; otherwise return ``False``."""
        with self._session() as session:
            record = session.run(
                statements.UPSERT_RELATION,
                subject_id=entity_identifier(relation.subject),
                object_id=entity_identifier(relation.object),
                kind=relation.predicate,
                rationale=relation.rationale,
                doc_label=relation.source_label,
            ).single()
        linked = bool(record and record.get("linked"))
        if not linked:
            logger.warning(
                "Skipped relation %s -> %s: an endpoint is not in the graph",
                relation.subject,
                relation.object,
            )
        return linked

    # -- reads ----------------------------------------------------------------

    def locate_entry_points(self, terms: list[str], limit: int) -> list[dict[str, Any]]:
        """Return candidate nodes whose text matches any of the given terms."""
        if not terms:
            return []
        with self._session() as session:
            cursor = session.run(
                statements.SEARCH_ENTRY_POINTS, terms=terms, limit=limit
            )
            return [dict(record) for record in cursor]

    def grow_neighbourhood(self, seed_id: str, depth: int, window: int) -> list[dict[str, Any]]:
        """Walk up to ``depth`` hops from one seed and describe each route."""
        with self._session() as session:
            cursor = session.run(
                statements.expansion_query(depth),
                seed_id=seed_id,
                window=window,
            )
            results: list[dict[str, Any]] = []
            for record in cursor:
                route = record.get("route")
                node_chain, edge_chain = self._decompose_path(route)
                if len(node_chain) < 2:
                    continue
                hop = node_chain[-1]
                results.append(
                    {
                        "name": hop.get("name", ""),
                        "kind": hop.get("kind", ""),
                        "summary": hop.get("summary", ""),
                        "doc_label": hop.get("doc_ref", ""),
                        "excerpt": hop.get("excerpt", ""),
                        "route": self._route_labels(node_chain, edge_chain),
                    }
                )
            return results

    @staticmethod
    def _decompose_path(path: Any) -> tuple[list[Node], list[Relationship]]:
        # A Neo4j Path exposes ordered .nodes / .relationships attributes;
        # plain iteration over the object is not guaranteed to yield nodes.
        try:
            nodes = list(path.nodes)
            edges = list(path.relationships)
        except AttributeError:
            nodes, edges = [], []
            for element in path or []:
                if isinstance(element, Node):
                    nodes.append(element)
                elif isinstance(element, Relationship):
                    edges.append(element)
        return nodes, edges

    @staticmethod
    def _route_labels(nodes: list[Node], edges: list[Relationship]) -> tuple[str, ...]:
        steps: list[str] = []
        for index, edge in enumerate(edges):
            left = nodes[index].get("name", "?")
            right = nodes[index + 1].get("name", "?")
            kind = edge.get("kind") if "kind" in edge else "?"
            steps.append(f"{left} --[{kind}]-- {right}")
        return tuple(steps)

    # -- overview --------------------------------------------------------------

    def overview(self) -> StoreOverview:
        with self._session() as session:
            node_count = session.run(statements.COUNT_NODES).single()["total"]
            edge_count = session.run(statements.COUNT_EDGES).single()["total"]
            raw_labels = session.run(statements.DISTINCT_SOURCES).single()["labels"]
        sources = tuple(
            label for label in raw_labels if label and str(label).strip()
        )
        return StoreOverview(
            node_count=node_count,
            edge_count=edge_count,
            sources=sources,
        )

    def wipe(self) -> None:
        """Delete every node and relationship currently in the database."""
        with self._session() as session:
            session.run(statements.WIPE_GRAPH)
        logger.warning("Knowledge graph wiped")
