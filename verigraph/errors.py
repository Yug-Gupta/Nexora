"""Application error taxonomy.

Errors raised across the library carry a ``message`` that is safe to show
to end users in the interface.  Technical details travel separately in
``detail`` and are intended for logs rather than the UI.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for every error the application raises itself."""

    def __init__(self, message: str, *, detail: str = ""):
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class UserInputError(AppError):
    """The caller supplied something unusable (empty question, blank text...)."""


class StorageError(AppError):
    """Anything that goes wrong talking to the graph database."""


class InferenceError(AppError):
    """Anything that goes wrong talking to the local language model."""


class SourceError(AppError):
    """The submitted document could not be turned into graph data."""


class ContextError(AppError):
    """Retrieval could not assemble enough evidence to answer a question."""


def translate_storage_failure(exc: Exception) -> StorageError:
    """Map a driver exception onto a user-friendly :class:`StorageError`.

    The Neo4j driver raises distinct exception subclasses for broken
    credentials, unreachable servers and malformed queries; we translate
    the most common ones into actionable wording before they reach the UI.
    """
    try:
        from neo4j.exceptions import AuthError, ServiceUnavailable, SessionExpired

        if isinstance(exc, AuthError):
            return StorageError(
                "Neo4j rejected the credentials. Check the user name and password.",
                detail=f"{type(exc).__name__}: {exc}",
            )
        if isinstance(exc, (ServiceUnavailable, SessionExpired)):
            return StorageError(
                "Could not reach the Neo4j server at the configured address.",
                detail=f"{type(exc).__name__}: {exc}",
            )
    except ImportError:
        pass

    kind = type(exc).__name__
    if "Auth" in kind:
        message = "Neo4j rejected the credentials. Check the user name and password."
    elif "Unavailable" in kind or "Timeout" in kind:
        message = "Could not reach the Neo4j server at the configured address."
    else:
        message = "The graph database reported a problem while running a query."
    return StorageError(message, detail=f"{kind}: {exc}")


def translate_inference_failure(exc: Exception) -> InferenceError:
    """Map an Ollama SDK failure onto a user-friendly :class:`InferenceError`."""
    kind = type(exc).__name__
    lowered = str(exc).lower()
    if "connect" in lowered or "connection" in lowered or isinstance(
        exc, ConnectionError
    ):
        message = "Could not reach the Ollama service. Is it running?"
    elif "not found" in lowered or "pull" in lowered:
        message = "The requested model is not installed on the Ollama server."
    else:
        message = "The local language model could not complete the request."
    return InferenceError(message, detail=f"{kind}: {exc}")
