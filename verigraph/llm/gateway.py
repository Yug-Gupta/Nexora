"""Thin, well-bounded wrapper around the Ollama client.

Every call into Ollama passes through :class:`InferenceGateway` so that
connection errors, missing models and empty replies are translated into
:class:`~verigraph.errors.InferenceError` in exactly one place.
"""

from __future__ import annotations

import logging

import ollama
from ollama import Client as OllamaClient

from verigraph.errors import InferenceError, translate_inference_failure

logger = logging.getLogger(__name__)


class InferenceGateway:
    """Convenience facade over the Ollama chat API."""

    def __init__(self, base_url: str, default_model: str) -> None:
        self._client = OllamaClient(host=base_url)
        self.default_model = default_model
        logger.debug("Inference gateway targets %s", base_url)

    def available_models(self) -> list[str]:
        """Return the model tags currently installed on the server."""
        try:
            response = self._client.list()
        except Exception as exc:
            raise translate_inference_failure(exc) from exc
        models = []
        for item in response.get("models", []):
            tag = item.get("model") or item.get("name") or ""
            if tag:
                models.append(tag)
        return sorted(models)

    def model_is_installed(self, model_name: str | None = None) -> bool:
        """Check whether a tag exists, tolerating the ``:latest`` suffix."""
        wanted = (model_name or self.default_model).strip()
        base, _, tag = wanted.partition(":")
        for installed in self.available_models():
            if installed == wanted:
                return True
            installed_base, _, installed_tag = installed.partition(":")
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
        """Send one user turn and return the raw reply text."""
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
                # Older SDK builds reject the format argument; retry plainly.
                response = self._client.chat(model=model, messages=messages)
        except Exception as exc:
            raise translate_inference_failure(exc) from exc

        text = (response.get("message") or {}).get("content", "").strip()
        if not text:
            raise InferenceError("The local model returned an empty response.")
        return text
