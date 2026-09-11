"""Thin, well-bounded wrapper around the Google Gemini API (``google-genai``).

Every model call passes through :class:`InferenceGateway` so that transport
errors, invalid or missing credentials, rate limits, timeouts and empty replies
are translated into :class:`~nexora.errors.InferenceError` in exactly one place.

The gateway deliberately exposes the same application-facing surface the rest
of Nexora has always used — ``complete``, ``available_models`` and
``model_is_installed`` — so the UI and the extraction/answering pipeline stay
completely provider-agnostic. Swapping the model provider only touches this
module, :mod:`nexora.config` and :mod:`nexora.errors`.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from google import genai
from google.genai import types

from nexora.errors import InferenceError, translate_inference_failure

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY_SECONDS = 1.0


def _model_short_name(value: Any) -> str:
    """Normalise a Gemini identifier (``models/gemini-x`` -> ``gemini-x``)."""
    text = str(value or "").strip()
    prefix = "models/"
    if text.startswith(prefix):
        text = text[len(prefix) :]
    return text


def _extract_candidate_text(candidates: Any) -> str:
    """Concatenate text parts from a response's ``candidates`` collection."""
    chunks: list[str] = []
    for candidate in candidates or []:
        if isinstance(candidate, dict):
            content = candidate.get("content")
        else:
            content = getattr(candidate, "content", None)
        if isinstance(content, dict):
            parts = content.get("parts")
        else:
            parts = getattr(content, "parts", None)
        for part in parts or []:
            if isinstance(part, dict):
                chunk = part.get("text")
            else:
                chunk = getattr(part, "text", None)
            if chunk:
                chunks.append(str(chunk))
    return "".join(chunks)


def _extract_response_text(response: Any) -> str:
    """Return the generated text from a ``generate_content`` response.

    The SDK exposes a convenient ``.text`` property, but very old or mocked
    responses may only carry ``candidates``; both are supported.
    """
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        text = response.get("text")
        if isinstance(text, str) and text:
            return text
        return _extract_candidate_text(response.get("candidates") or [])
    text = getattr(response, "text", None)
    if isinstance(text, str) and text:
        return text
    return _extract_candidate_text(getattr(response, "candidates", None) or [])


def _extract_model_names(response: Any) -> list[str]:
    """Return sorted, de-duplicated, prefix-free model names from ``models.list``."""
    if isinstance(response, dict):
        raw: Any = response.get("models", []) or []
    else:
        raw = getattr(response, "models", None)
        if raw is None:
            raw = response  # a pager / iterable of Model objects
    try:
        items = list(raw)
    except TypeError:
        return []

    names: list[str] = []
    for item in items:
        if isinstance(item, dict):
            name = item.get("name")
        else:
            name = getattr(item, "name", None)
        short = _model_short_name(name)
        if short and short not in names:
            names.append(short)
    return sorted(names)


def _is_retryable_inference_failure(exc: Exception) -> bool:
    """Return whether a Gemini failure is likely temporary."""
    code = getattr(exc, "code", None)
    if isinstance(code, int) and code in {500, 502, 503, 504}:
        return True
    lowered = str(exc).lower()
    return any(
        phrase in lowered
        for phrase in ("temporarily unavailable", "service unavailable", "overloaded")
    )


class InferenceGateway:
    """Convenience facade over the Google Gemini generative-model API."""

    def __init__(
        self,
        api_key: str,
        default_model: str,
        timeout_seconds: float = 300.0,
        *,
        client: Any | None = None,
    ) -> None:
        self.default_model = default_model
        self._api_key = (api_key or "").strip()
        if client is not None:
            self._client: Any | None = client
        elif self._api_key:
            self._client = self._build_client(timeout_seconds)
        else:
            self._client = None
        logger.debug(
            "Inference gateway configured (model=%s, api_key=%s)",
            default_model,
            "set" if self._api_key else "missing",
        )

    def _build_client(self, timeout_seconds: float) -> Any:
        timeout_ms = max(1, int(timeout_seconds * 1000))
        try:
            return genai.Client(
                api_key=self._api_key,
                http_options=types.HttpOptions(timeout=timeout_ms),
            )
        except TypeError:
            # Older SDK builds may not forward a timeout option.
            return genai.Client(api_key=self._api_key)

    def is_configured(self) -> bool:
        """Return ``True`` when an API key is present (the key is never returned)."""
        return self._client is not None

    def _require_client(self) -> Any:
        if self._client is None:
            raise InferenceError(
                "The Gemini API key is not configured. Set GEMINI_API_KEY and "
                "try again."
            )
        return self._client

    def available_models(self) -> list[str]:
        """Return the model names the configured API key can use."""
        client = self._require_client()
        try:
            response = client.models.list()
        except Exception as exc:
            raise translate_inference_failure(exc) from exc
        return _extract_model_names(response)

    def model_is_installed(
        self,
        model_name: str | None = None,
        *,
        installed: list[str] | None = None,
    ) -> bool:
        """Check whether a model name is present in the available model list.

        ``installed`` may be supplied when the caller already holds a fresh list
        (e.g. from :meth:`available_models`), avoiding a second API round-trip.
        """
        wanted = _model_short_name(model_name or self.default_model)
        if not wanted:
            return False
        if installed is None:
            installed = self.available_models()
        return wanted in {_model_short_name(name) for name in installed}

    def complete(
        self,
        prompt: str,
        model_name: str | None = None,
        *,
        expect_json: bool = False,
    ) -> str:
        """Send one prompt and return the raw reply text.

        When ``expect_json`` is set the Gemini API is asked to constrain the
        response to valid JSON (`response_mime_type`), which keeps entity and
        relationship extraction reliable. Automatic function calling is always
        disabled: Nexora only ever wants text back, and leaving it on makes the
        SDK log a warning on every call.
        """
        client = self._require_client()
        model = _model_short_name(model_name or self.default_model)
        config = types.GenerateContentConfig(
            response_mime_type="application/json" if expect_json else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )
        for attempt in range(_MAX_RETRIES):
            try:
                response = client.models.generate_content(
                    model=model, contents=prompt, config=config
                )
                break
            except Exception as exc:
                if (
                    not _is_retryable_inference_failure(exc)
                    or attempt == _MAX_RETRIES - 1
                ):
                    raise translate_inference_failure(exc) from exc
                delay = _RETRY_BASE_DELAY_SECONDS * (2**attempt)
                logger.warning(
                    "Gemini request failed temporarily; retrying in %.1f seconds",
                    delay,
                )
                time.sleep(delay)

        text = _extract_response_text(response).strip()
        if not text:
            raise InferenceError("The Gemini API returned an empty response.")
        return text
