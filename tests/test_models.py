"""Tests for nexora.models - domain records and stable identifiers."""

from __future__ import annotations

from nexora.models import (
    Entity,
    HealthProbe,
    ProvenanceRecord,
    StoreOverview,
    entity_identifier,
    truncate,
)


def test_entity_identifier_is_stable_and_case_insensitive():
    assert entity_identifier("Priya Anand") == entity_identifier("priya anand")
    assert entity_identifier("Priya  Anand") == entity_identifier("Priya Anand")


def test_entity_identifier_distinguishes_entities():
    assert entity_identifier("Aster Systems") != entity_identifier("Aster")
    assert entity_identifier("Aster Systems").startswith("ent:")


def test_truncate_edge_cases():
    assert truncate(None) == ""
    assert truncate("") == ""
    assert truncate("short text") == "short text"
    long = "word " * 100
    result = truncate(long, limit=20)
    assert len(result) <= 20
    assert result.endswith("…")
    assert truncate("a   b\nc", limit=50) == "a b c"


def test_domain_records_defaults():
    assert HealthProbe(component="x", available=True).extra == ()
    overview = StoreOverview()
    assert overview.node_count == 0
    assert overview.document_count == 0
    assert overview.sources == ()
    entity = Entity(name="Cirrus", kind="PRODUCT")
    assert entity.summary == ""
    record = ProvenanceRecord(index=1, entity="x", document="d", quote="q")
    assert record.route == ()


def test_ingest_report_counts():
    from nexora.models import IngestReport

    report = IngestReport(
        source_label="s",
        entity_count=3,
        relation_count=2,
        dropped_relations=1,
        entities=(Entity(name="a", kind="PERSON"),),
    )
    assert report.entity_count == 3
    assert len(report.entities) == 1
