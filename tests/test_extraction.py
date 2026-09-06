"""Tests for the extraction stage - robust handling of LLM output."""

from __future__ import annotations

import json

import pytest
from nexora.errors import InferenceError, SourceError
from nexora.pipeline.extraction import (
    _locate_json_payload,
    _parse_entities,
    _parse_model_object,
    _parse_relations,
    extract_graph_elements,
)

DOC = "Aster Systems built Cirrus. Priya Anand founded Aster Systems in 2018."
LABEL = "sample-doc"


class _FakeGateway:
    def __init__(self, reply: str = "", error: Exception | None = None):
        self.reply = reply
        self.error = error
        self.calls: list[dict] = []

    def complete(self, prompt, model_name=None, *, expect_json=False):
        self.calls.append({"model_name": model_name, "expect_json": expect_json})
        if self.error is not None:
            raise self.error
        return self.reply


def _payload():
    return {
        "entities": [
            {
                "name": "Aster Systems",
                "type": "ORGANIZATION",
                "summary": "a climate company",
            },
            {"name": "Priya Anand", "type": "PERSON", "summary": "founder"},
            {"name": "Cirrus", "type": "product", "summary": "weather platform"},
        ],
        "relations": [
            {
                "source": "Aster Systems",
                "target": "Cirrus",
                "type": "built",
                "context": "Aster built Cirrus",
            },
            {
                "source": "Priya Anand",
                "target": "Aster Systems",
                "type": "founded",
                "context": "founder",
            },
        ],
    }


def test_extract_graph_elements_happy_path():
    gateway = _FakeGateway(reply=json.dumps(_payload()))
    entities, relations = extract_graph_elements(DOC, LABEL, gateway)
    assert [e.name for e in entities] == ["Aster Systems", "Priya Anand", "Cirrus"]
    assert entities[2].kind == "PRODUCT"
    assert len(relations) == 2
    assert gateway.calls[0]["expect_json"] is True


def test_locale_json_payload_strips_fences_and_prose():
    wrapped = (
        "Here is your result:\n```json\n" + json.dumps(_payload()) + "\n```\nDone."
    )
    parsed = json.loads(_locate_json_payload(wrapped))
    assert parsed["entities"][0]["name"] == "Aster Systems"


def test_parse_model_object_rejects_malformed_json():
    with pytest.raises(SourceError):
        _parse_model_object("this is not json at all")


def test_parse_entities_dedupes_and_applies_aliases():
    payload = {
        "entities": [
            {"name": "Aster Systems", "type": "ORGANIZATION"},
            {"label": "Aster Systems", "kind": "person"},  # duplicate via alias
            {"name": "  ", "type": "PERSON"},  # blank name ignored
            {"name": "Priya Anand"},  # missing type -> CONCEPT default
        ]
    }
    entities = _parse_entities(payload, LABEL, DOC)
    assert [e.name for e in entities] == ["Aster Systems", "Priya Anand"]
    assert entities[0].kind == "ORGANIZATION"
    assert entities[1].kind == "CONCEPT"


def test_parse_relations_filters_unknown_endpoints_and_self_loops():
    payload = {
        "entities": [{"name": "Aster Systems", "type": "ORGANIZATION"}],
        "relations": [
            {"source": "Aster Systems", "target": "Ghost", "type": "owns"},
            {"source": "Aster Systems", "target": "aster systems", "type": "self"},
            {"from": "Aster Systems", "to": "Cirrus", "type": "built"},
            {"source": "Aster Systems", "target": "Cirrus", "type": "built"},
        ],
    }
    known = {"aster systems"}
    relations = _parse_relations(payload, LABEL, known)
    # The only valid candidate references Cirrus which is not in `known`, so
    # nothing survives when the endpoint is unknown.
    assert relations == []


def test_parse_relations_deduplicates_and_normalises():
    payload = {
        "relations": [
            {"source": "A", "target": "B", "type": "works at", "context": "x"},
            {"subject": "A", "object": "B", "relation": "works at", "context": "y"},
            {"from": "A", "to": "B", "type": "LEADS"},
        ]
    }
    known = {"a", "b"}
    relations = _parse_relations(payload, LABEL, known)
    assert len(relations) == 2
    assert relations[0].predicate == "WORKS AT"
    assert {r.predicate for r in relations} == {"WORKS AT", "LEADS"}


def test_no_entities_raises_source_error():
    gateway = _FakeGateway(reply=json.dumps({"entities": [], "relations": []}))
    with pytest.raises(SourceError):
        extract_graph_elements(DOC, LABEL, gateway)


def test_inference_failure_is_wrapped_as_source_error():
    gateway = _FakeGateway(error=InferenceError("boom", detail="connection refused"))
    with pytest.raises(SourceError) as excinfo:
        extract_graph_elements(DOC, LABEL, gateway)
    assert "could not analyse" in excinfo.value.message
    assert excinfo.value.detail == "connection refused"


def test_malformed_reply_raises_source_error():
    gateway = _FakeGateway(reply="No entities here at all")
    with pytest.raises(SourceError):
        extract_graph_elements(DOC, LABEL, gateway)
