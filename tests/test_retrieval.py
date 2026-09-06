"""Tests for retrieval: keyword derivation, seed ranking and context building."""

from __future__ import annotations

import pytest
from nexora.config import Settings
from nexora.errors import ContextError
from nexora.pipeline.retrieval import _rank_seeds, collect_context, derive_terms


class FakeStore:
    """Duck-typed stand-in for KnowledgeBase used by collect_context."""

    def __init__(self, seeds=None, neighbours=None):
        self._seeds = seeds or []
        self._neighbours = neighbours or {}  # entity_id -> rows
        self.entry_calls = 0

    def locate_entry_points(self, terms, limit):
        self.entry_calls += 1
        return list(self._seeds[:limit])

    def grow_neighbourhood(self, seed_id, depth, window):
        return list(self._neighbours.get(seed_id, []))


def _seed(name, entity_id=None, kind="PERSON", summary=""):
    return {
        "entity_id": entity_id or name.lower(),
        "name": name,
        "kind": kind,
        "summary": summary,
        "doc_label": "doc",
        "excerpt": "excerpt",
    }


def test_derive_terms_filters_stopwords_and_short_tokens():
    terms = derive_terms("Who founded Aster Systems and when did it happen?")
    assert "who" not in terms
    assert "and" not in terms
    assert "founded" in terms
    assert "aster" in terms
    assert "systems" in terms
    assert all(len(t) >= 3 for t in terms)


def test_derive_terms_empty_for_stopword_only():
    assert derive_terms("is it what?") == []


def test_rank_seeds_prefers_high_matching_terms():
    seeds = [
        _seed("Weather Bureau", kind="ORGANIZATION", summary="forecasting in Oslo"),
        _seed("Priya Anand", kind="PERSON", summary="data science at Meridian"),
    ]
    terms = ["priya", "data"]
    ranked = _rank_seeds(seeds, terms)
    assert ranked[0]["name"] == "Priya Anand"


def test_rank_seeds_ties_break_alphabetically():
    seeds = [_seed("Zebra"), _seed("Alpha")]
    assert [s["name"] for s in _rank_seeds(seeds, ["nothing"])] == ["Alpha", "Zebra"]


def test_collect_context_returns_pieces_and_audit():
    store = FakeStore(
        seeds=[
            _seed(
                "Aster Systems",
                entity_id="ast",
                kind="ORGANIZATION",
                summary="climate analytics",
            ),
        ],
        neighbours={
            "ast": [
                {
                    "name": "Cirrus",
                    "kind": "PRODUCT",
                    "summary": "weather platform",
                    "doc_label": "doc1",
                    "excerpt": "ex",
                    "route": ("Aster Systems --[built]-- Cirrus",),
                }
            ]
        },
    )
    settings = Settings(retrieval_depth=2, context_cap=10, entry_limit=8)
    pieces, seeds, audit = collect_context("Who built Cirrus?", store, settings)
    assert [p.name for p in pieces] == ["Aster Systems", "Cirrus"]
    assert pieces[1].route == ("Aster Systems --[built]-- Cirrus",)
    assert seeds == ["Aster Systems"]
    assert any("Search terms" in line for line in audit)
    assert any("2 context entries" in line for line in audit)


def test_collect_context_no_seeds_raises():
    store = FakeStore(seeds=[])
    with pytest.raises(ContextError):
        collect_context("Who founded Aster?", store, Settings())


def test_collect_context_no_terms_raises():
    store = FakeStore(seeds=[_seed("X")])
    with pytest.raises(ContextError):
        collect_context("is it what", store, Settings())


def test_collect_context_dedupes_by_name():
    store = FakeStore(
        seeds=[_seed("Shared", entity_id="a"), _seed("Shared", entity_id="b")],
        neighbours={
            "a": [
                {
                    "name": "Shared",
                    "kind": "X",
                    "summary": "",
                    "doc_label": "",
                    "excerpt": "",
                    "route": (),
                }
            ],
            "b": [],
        },
    )
    pieces, _, _ = collect_context("shared thing", store, Settings(context_cap=10))
    names = [p.name for p in pieces]
    assert len(names) == len(set(names))


def _neighbour(name):
    return {
        "name": name,
        "kind": "PERSON",
        "summary": "",
        "doc_label": "doc",
        "excerpt": "",
        "route": (),
    }


class _CountingStore(FakeStore):
    """FakeStore that records which seeds were actually expanded."""

    def __init__(self, seeds=None, neighbours=None):
        super().__init__(seeds=seeds, neighbours=neighbours)
        self.expanded = []

    def grow_neighbourhood(self, seed_id, depth, window):
        self.expanded.append(seed_id)
        return super().grow_neighbourhood(seed_id, depth, window)


def test_collect_context_stops_expanding_once_cap_is_reached():
    store = _CountingStore(
        seeds=[_seed("SeedA", entity_id="a"), _seed("SeedB", entity_id="b")],
        neighbours={"a": [_neighbour(f"N{i}") for i in range(6)]},
    )
    pieces, _, _ = collect_context("seed a b", store, Settings(context_cap=4))
    assert len(pieces) == 4
    # SeedB must never be expanded once the context cap was filled by SeedA.
    assert store.expanded == ["a"]
