"""Application error taxonomy for Nexora.

Errors raised across the package carry a ``message`` that is safe to show to
end users in the interface.  Technical details travel separately in
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
    """Anything that goes wrong talking to the language-model provider."""


class SourceError(AppError):
    """The submitted document could not be turned into graph data."""


class ContextError(AppError):
    """Retrieval could not assemble enough evidence to answer a question."""


def translate_storage_failure(exc: Exception) -> StorageError:
    """Map a driver exception onto a user-friendly :class:`StorageError`.

    The Neo4j driver raises distinct exception subclasses for broken
    credentials, unreachable servers and malformed queries; the most common
    ones are translated into actionable wording before they reach the UI.
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
    except ImportError:  # driver not installed yet
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
    """Map a Gemini (``google-genai``) failure onto a friendly error.

    The SDK raises ``ClientError`` for 4xx responses (bad key, bad request,
    rate limits) and ``ServerError`` for 5xx, both carrying a numeric ``code``.
    Network problems surface as transport exceptions. The API key is never
    included in the message or the detail.
    """
    kind = type(exc).__name__
    lowered = str(exc).lower()
    code = getattr(exc, "code", None)

    is_client_error = False
    is_server_error = False
    try:
        from google.genai import errors as genai_errors

        is_client_error = isinstance(exc, genai_errors.ClientError)
        is_server_error = isinstance(exc, genai_errors.ServerError)
    except ImportError:  # SDK not installed yet
        lowered_kind = kind.lower()
        is_client_error = "clienterror" in lowered_kind
        is_server_error = "servererror" in lowered_kind

    if (
        code == 429
        or "rate limit" in lowered
        or "quota" in lowered
        or "resource_exhausted" in lowered
    ):
        message = "The Gemini API rate limit was reached. Wait a moment and try again."
    elif code in (401, 403) or "api key" in lowered or "permission" in lowered:
        message = "The Gemini API key was rejected. Check that GEMINI_API_KEY is valid."
    elif code == 400 or "invalid" in lowered:
        message = (
            "The Gemini API rejected the request. Check the configured model and input."
        )
    elif is_server_error or (isinstance(code, int) and code >= 500):
        message = "The Gemini API is temporarily unavailable. Please try again shortly."
    elif "timeout" in lowered or "timed out" in lowered:
        message = (
            "The Gemini API took too long to answer. Try again or use a faster model."
        )
    elif (
        "connect" in lowered
        or "connection" in lowered
        or isinstance(exc, ConnectionError)
    ):
        message = "Could not reach the Gemini API. Check your network connection."
    elif "not found" in lowered or "does not exist" in lowered:
        message = "The requested Gemini model is not available for this API key."
    elif is_client_error:
        message = "The Gemini API rejected the request. Check your configuration."
    else:
        message = "The Gemini API could not complete the request."
    return InferenceError(message, detail=f"{kind}: {exc}")
