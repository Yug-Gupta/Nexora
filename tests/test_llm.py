"""Tests for prompt assembly and the Gemini inference gateway.

No network access: the gateway is built with an injected fake client.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from nexora.errors import InferenceError
from nexora.llm import gateway
from nexora.llm.gateway import InferenceGateway
from nexora.llm.prompts import (
    ALLOWED_ENTITY_TYPES,
    build_answer_prompt,
    build_extraction_prompt,
    format_context_piece,
)
from nexora.models import ContextPiece


def test_build_extraction_prompt_contains_document_and_schema():
    prompt = build_extraction_prompt("The document body here.")
    assert "The document body here." in prompt
    assert '"entities"' in prompt
    assert '"relations"' in prompt
    assert "PERSON" in prompt


def test_format_context_piece_numbers_entries():
    piece = ContextPiece(
        name="Cirrus",
        kind="PRODUCT",
        summary="weather platform",
        document="doc-1",
        route=("A --[built]-- Cirrus",),
    )
    line = format_context_piece(1, piece)
    assert line.startswith("[1] Entity: Cirrus (PRODUCT)")
    assert "weather platform" in line
    assert "doc-1" in line
    assert "A --[built]-- Cirrus" in line


def test_format_context_piece_tolerates_empty_fields():
    piece = ContextPiece(name="X", kind="", summary="", document="")
    line = format_context_piece(2, piece)
    assert line == "[2] Entity: X (UNKNOWN)"


def test_build_answer_prompt_lists_entries_and_question():
    pieces = [
        ContextPiece(
            name="Alice", kind="PERSON", summary="founder", document="d", route=()
        ),
    ]
    prompt = build_answer_prompt("Who is Alice?", pieces)
    assert "Who is Alice?" in prompt
    assert "[1] Entity: Alice" in prompt
    assert "QUESTION" in prompt


def test_allowed_entity_types_are_upper_case():
    assert ALLOWED_ENTITY_TYPES
    assert all(t == t.upper() for t in ALLOWED_ENTITY_TYPES)


# --- response / model-name extraction ----------------------------------------


def test_model_short_name_strips_prefix():
    assert gateway._model_short_name("models/gemini-2.5-flash") == "gemini-2.5-flash"
    assert gateway._model_short_name("gemini-2.5-flash") == "gemini-2.5-flash"
    assert gateway._model_short_name(None) == ""


def test_extract_response_text_from_text_attribute():
    assert gateway._extract_response_text(SimpleNamespace(text="hello")) == "hello"


def test_extract_response_text_from_candidates():
    part = SimpleNamespace(text="from parts")
    candidate = SimpleNamespace(content=SimpleNamespace(parts=[part]))
    response = SimpleNamespace(text=None, candidates=[candidate])
    assert gateway._extract_response_text(response) == "from parts"


def test_extract_response_text_from_dict():
    assert gateway._extract_response_text({"text": "dict text"}) == "dict text"


def test_extract_response_text_empty():
    assert gateway._extract_response_text(SimpleNamespace(text=None)) == ""
    assert gateway._extract_response_text(None) == ""


def test_extract_model_names_from_objects_strips_prefix():
    response = SimpleNamespace(
        models=[
            SimpleNamespace(name="models/gemini-2.5-pro"),
            SimpleNamespace(name="models/gemini-2.5-flash"),
            SimpleNamespace(name=None),
        ]
    )
    assert gateway._extract_model_names(response) == [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
    ]


def test_extract_model_names_from_dict():
    response = {"models": [{"name": "models/gemini-2.0-flash"}]}
    assert gateway._extract_model_names(response) == ["gemini-2.0-flash"]


# --- gateway behaviour with an injected fake client --------------------------


class _FakeModels:
    def __init__(self, text: str = "", models=None, error: Exception | None = None):
        self._text = text
        self._models = models or []
        self._error = error
        self.last_call: dict | None = None

    def generate_content(self, *, model, contents, config=None):
        self.last_call = {"model": model, "contents": contents, "config": config}
        if self._error is not None:
            raise self._error
        return SimpleNamespace(text=self._text)

    def list(self):
        if self._error is not None:
            raise self._error
        return SimpleNamespace(models=self._models)


class _FakeClient:
    def __init__(self, models: _FakeModels):
        self.models = models


def _gateway(models: _FakeModels, **kwargs) -> InferenceGateway:
    return InferenceGateway(
        api_key="test-key",
        default_model="gemini-2.5-flash",
        client=_FakeClient(models),
        **kwargs,
    )


class _ApiBoom(Exception):
    def __init__(self, code: int, message: str = "boom"):
        super().__init__(message)
        self.code = code


def test_complete_returns_stripped_text():
    fake = _FakeModels(text="  generated answer  ")
    assert _gateway(fake).complete("prompt") == "generated answer"


def test_complete_requests_json_mode_when_expected():
    fake = _FakeModels(text="{}")
    _gateway(fake).complete("prompt", expect_json=True)
    assert fake.last_call is not None
    config = fake.last_call["config"]
    assert getattr(config, "response_mime_type", None) == "application/json"


def test_complete_disables_automatic_function_calling():
    fake = _FakeModels(text="answer")
    _gateway(fake).complete("prompt")
    assert fake.last_call is not None
    config = fake.last_call["config"]
    assert config is not None
    assert getattr(config, "response_mime_type", "unset") is None
    afc = getattr(config, "automatic_function_calling", None)
    assert afc is not None and afc.disable is True


def test_complete_uses_configured_model_and_normalises_name():
    fake = _FakeModels(text="answer")
    _gateway(fake).complete("prompt", model_name="models/gemini-2.5-pro")
    assert fake.last_call is not None
    assert fake.last_call["model"] == "gemini-2.5-pro"


def test_complete_empty_response_raises_inference_error():
    fake = _FakeModels(text="")
    with pytest.raises(InferenceError):
        _gateway(fake).complete("prompt")


def test_complete_translates_rate_limit():
    fake = _FakeModels(error=_ApiBoom(429, "quota exceeded"))
    with pytest.raises(InferenceError) as excinfo:
        _gateway(fake).complete("prompt")
    assert "rate limit" in excinfo.value.message.lower()


def test_complete_translates_server_error():
    fake = _FakeModels(error=_ApiBoom(503, "unavailable"))
    with pytest.raises(InferenceError) as excinfo:
        _gateway(fake).complete("prompt")
    assert "unavailable" in excinfo.value.message.lower()


def test_complete_translates_auth_error_without_leaking_key():
    fake = _FakeModels(error=_ApiBoom(403, "permission denied"))
    with pytest.raises(InferenceError) as excinfo:
        _gateway(fake).complete("prompt")
    assert "api key" in excinfo.value.message.lower()
    assert "test-key" not in excinfo.value.message
    assert "test-key" not in excinfo.value.detail


def test_complete_translates_connection_error():
    fake = _FakeModels(error=ConnectionError("connection refused"))
    with pytest.raises(InferenceError) as excinfo:
        _gateway(fake).complete("prompt")
    assert "reach" in excinfo.value.message.lower()


def test_missing_api_key_is_reported_and_never_leaks():
    gw = InferenceGateway(api_key="", default_model="gemini-2.5-flash")
    assert gw.is_configured() is False
    with pytest.raises(InferenceError) as excinfo:
        gw.complete("prompt")
    assert "GEMINI_API_KEY" in excinfo.value.message
    with pytest.raises(InferenceError):
        gw.available_models()


def test_available_models_returns_normalised_names():
    fake = _FakeModels(
        models=[
            SimpleNamespace(name="models/gemini-2.5-pro"),
            SimpleNamespace(name="models/gemini-2.5-flash"),
        ]
    )
    assert _gateway(fake).available_models() == [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
    ]


def test_available_models_translates_errors():
    fake = _FakeModels(error=_ApiBoom(403, "permission denied"))
    with pytest.raises(InferenceError):
        _gateway(fake).available_models()


def test_model_is_installed_matches_exact_and_prefixed_names():
    fake = _FakeModels(models=[SimpleNamespace(name="models/gemini-2.5-flash")])
    gw = _gateway(fake)
    assert gw.model_is_installed("gemini-2.5-flash") is True
    assert gw.model_is_installed("models/gemini-2.5-flash") is True
    assert gw.model_is_installed("gemini-2.5-pro") is False


def test_model_is_installed_uses_supplied_list_without_client_call():
    fake = _FakeModels()
    gw = _gateway(fake)
    assert gw.model_is_installed("gemini-2.5-pro", installed=["gemini-2.5-pro"]) is True
    assert fake.last_call is None
