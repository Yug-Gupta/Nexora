"""Thin, well-bounded wrapper around the Ollama client.

Every call into Ollama passes through :class:`InferenceGateway` so that
connection errors, missing models, timeouts and empty replies are translated
into :class:`~nexora.errors.InferenceError` in exactly one place.

The gateway tolerates both response conventions shipped by the Ollama SDK:
recent versions return typed models (``ChatResponse`` / ``ListResponse``)
while older ones return plain dictionaries, so Nexora keeps working across
SDK versions.
"""

from __future__ import annotations

import logging
from typing import Any

from ollama import Client as OllamaClient

from nexora.errors import InferenceError, translate_inference_failure

logger = logging.getLogger(__name__)


def _extract_chat_content(response: Any) -> str:
    """Return the assistant text from a chat response object or dict."""
    if isinstance(response, dict):
        message = response.get("message") or {}
        if isinstance(message, dict):
            return str(message.get("content") or "")
        return str(getattr(message, "content", None) or "")
    message = getattr(response, "message", None)
    if message is None:
        return ""
    return str(getattr(message, "content", None) or "")


def _extract_model_tags(response: Any) -> list[str]:
    """Return installed model tags from a list response object or dict."""
    raw_models: list[Any] = []
    if isinstance(response, dict):
        raw_models = response.get("models", []) or []
    elif hasattr(response, "models"):
        raw_models = list(response.models)
    else:
        return []

    tags: list[str] = []
    for item in raw_models:
        if isinstance(item, dict):
            tag = item.get("model") or item.get("name") or ""
        else:
            tag = getattr(item, "model", None) or getattr(item, "name", None) or ""
        tag = str(tag).strip()
        if tag:
            tags.append(tag)
    return sorted(tags)


class InferenceGateway:
    """Convenience facade over the Ollama chat API."""

    def __init__(
        self,
        base_url: str,
        default_model: str,
        timeout_seconds: float = 300.0,
    ) -> None:
        self.default_model = default_model
        try:
            self._client = OllamaClient(host=base_url, timeout=timeout_seconds)
        except TypeError:
            # Very old SDK builds did not forward a timeout to httpx.
            self._client = OllamaClient(host=base_url)
        logger.debug("Inference gateway targets %s", base_url)

    def available_models(self) -> list[str]:
        """Return the model tags currently installed on the server."""
        try:
            response = self._client.list()
        except Exception as exc:
            raise translate_inference_failure(exc) from exc
        return _extract_model_tags(response)

    def model_is_installed(
        self,
        model_name: str | None = None,
        *,
        installed: list[str] | None = None,
    ) -> bool:
        """Check whether a tag exists, tolerating the ``:latest`` suffix.

        ``installed`` may be passed in when the caller already holds a fresh
        model list (e.g. from :meth:`available_models`), avoiding a second
        round-trip to the Ollama server.
        """
        wanted = (model_name or self.default_model).strip()
        base, _, tag = wanted.partition(":")
        if installed is None:
            installed = self.available_models()
        for current in installed:
            if current == wanted:
                return True
            installed_base, _, installed_tag = current.partition(":")
            if installed_base == base and (
                not tag or tag == installed_tag or installed_tag == "latest"
            ):
                return True
        return False

    def complete(
        self,
        prompt: str,
        model_name: str | None = None,
        *,
        expect_json: bool = False,
    ) -> str:
        """Send one user turn and return the raw reply text.

        When ``expect_json`` is set the SDK is asked to constrain output to
        JSON; clients that predate the option receive a plain retry.
        """
        model = model_name or self.default_model
        messages = [{"role": "user", "content": prompt}]
        kwargs: dict[str, object] = {}
        if expect_json:
            kwargs["format"] = "json"
        try:
            try:
                response = self._client.chat(model=model, messages=messages, **kwargs)
            except TypeError:
                if not expect_json:
                    raise
                response = self._client.chat(model=model, messages=messages)
        except Exception as exc:
            raise translate_inference_failure(exc) from exc

        text = _extract_chat_content(response).strip()
        if not text:
            raise InferenceError("The local model returned an empty response.")
        return text
