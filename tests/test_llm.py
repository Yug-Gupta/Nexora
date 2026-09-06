"""Tests for prompt assembly and gateway response handling."""

from __future__ import annotations

from types import SimpleNamespace

from nexora.llm.gateway import (
    _extract_chat_content,
    _extract_model_tags,
)
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


# --- gateway response extraction ---------------------------------------------


class _Msg:
    content = "plain-content"


class _DictLikeResponse:
    message = _Msg()


def test_extract_chat_content_from_attribute_object():
    assert _extract_chat_content(_DictLikeResponse()) == "plain-content"


def test_extract_chat_content_from_dict():
    response = {"message": {"content": "dict-content"}}
    assert _extract_chat_content(response) == "dict-content"


def test_extract_chat_content_missing_message():
    assert _extract_chat_content({"done": True}) == ""


def test_extract_model_tags_from_typed_objects():
    response = SimpleNamespace(
        models=[SimpleNamespace(model="llama3.2:latest"), SimpleNamespace(model=None)]
    )
    assert _extract_model_tags(response) == ["llama3.2:latest"]


def test_extract_model_tags_from_dicts():
    response = {"models": [{"model": "qwen2.5:7b"}, {"name": "nomic-embed-text"}]}
    assert _extract_model_tags(response) == ["nomic-embed-text", "qwen2.5:7b"]


def test_extract_model_tags_empty():
    assert _extract_model_tags({"models": []}) == []


class StaticGateway:
    """InferenceGateway stand-in that never touches the network."""

    def __init__(self, installed, default="llama3.2"):
        self.default_model = default
        self._installed = installed

    def available_models(self):
        return list(self._installed)

    def model_is_installed(self, model_name=None):
        from nexora.llm.gateway import InferenceGateway

        return InferenceGateway.model_is_installed(self, model_name)


def test_model_is_installed_exact_match():
    gateway = StaticGateway(["qwen2.5:7b"])
    assert gateway.model_is_installed("qwen2.5:7b")
    assert gateway.model_is_installed() is False  # default llama3.2 is not there


def test_model_is_installed_tolerates_latest_suffix():
    gateway = StaticGateway(["llama3.2:latest"])
    assert gateway.model_is_installed("llama3.2") is True


def test_model_is_installed_missing_model():
    gateway = StaticGateway(["nomic-embed-text"])
    assert gateway.model_is_installed("qwen2.5:7b") is False
