"""Ownership of the Neo4j driver connection.

:class:`Neo4jConnector` is the only place in the codebase that touches
``GraphDatabase.driver``.  Domain logic works against :class:`KnowledgeBase`
objects (``nexora.db.repository``), which in turn borrow a session from a
connector.
"""

from __future__ import annotations

import logging

from neo4j import GraphDatabase
from neo4j.exceptions import ConfigurationError

from nexora.errors import StorageError, translate_storage_failure

logger = logging.getLogger(__name__)


class Neo4jConnector:
    """Lazy wrapper around a Neo4j driver.

    The driver only opens a socket on first use, so constructing a connector
    never blocks or fails even when the server is offline.
    """

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str | None = None,
    ) -> None:
        self._database = database or None
        try:
            self._driver = GraphDatabase.driver(uri, auth=(user, password))
        except ConfigurationError as exc:
            raise StorageError(
                "The Neo4j connection URI is invalid.",
                detail=f"ConfigurationError: {exc}",
            ) from exc
        except Exception as exc:
            raise translate_storage_failure(exc) from exc
        logger.debug("Neo4j connector prepared for %s", uri)

    def session(self):
        """Open a new session bound to the configured database."""
        if self._database:
            return self._driver.session(database=self._database)
        return self._driver.session()

    def ping(self) -> None:
        """Force a trivial round-trip to prove the server is reachable."""
        try:
            with self.session() as session:
                session.run("RETURN 1").consume()
        except Exception as exc:
            raise translate_storage_failure(exc) from exc

    def close(self) -> None:
        try:
            self._driver.close()
        except Exception as exc:  # pragma: no cover - best effort cleanup
            logger.warning("Ignored error while closing driver: %s", exc)

    def __enter__(self) -> Neo4jConnector:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
