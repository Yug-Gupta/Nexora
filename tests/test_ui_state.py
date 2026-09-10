"""Tests for the Streamlit secrets -> environment bridge used on Cloud."""

from __future__ import annotations

import os

import streamlit as st
from nexora.ui import state


def _clear(monkeypatch, *keys: str) -> None:
    for key in keys:
        monkeypatch.delenv(key, raising=False)


def test_hydrate_sets_missing_environment_variables(monkeypatch):
    _clear(monkeypatch, "GEMINI_API_KEY", "NEO4J_URI")
    monkeypatch.setattr(
        st, "secrets", {"GEMINI_API_KEY": "abc", "NEO4J_URI": "bolt://aura:7687"}
    )
    applied = state.hydrate_environment_from_secrets()
    assert "GEMINI_API_KEY" in applied
    assert os.environ["GEMINI_API_KEY"] == "abc"
    assert os.environ["NEO4J_URI"] == "bolt://aura:7687"


def test_hydrate_respects_real_environment_precedence(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "from-env")
    monkeypatch.setattr(st, "secrets", {"GEMINI_API_KEY": "from-secret"})
    applied = state.hydrate_environment_from_secrets()
    assert os.environ["GEMINI_API_KEY"] == "from-env"
    assert "GEMINI_API_KEY" not in applied


def test_hydrate_ignores_unknown_secret_keys(monkeypatch):
    _clear(monkeypatch, "SOMETHING_ELSE")
    monkeypatch.setattr(st, "secrets", {"SOMETHING_ELSE": "x"})
    assert state.hydrate_environment_from_secrets() == ()
    assert "SOMETHING_ELSE" not in os.environ


def test_hydrate_tolerates_missing_keys(monkeypatch):
    class _Empty:
        def __getitem__(self, key):
            raise KeyError(key)

    monkeypatch.setattr(st, "secrets", _Empty())
    assert state.hydrate_environment_from_secrets() == ()
