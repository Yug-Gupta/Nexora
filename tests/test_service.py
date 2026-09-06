"""Tests for the service facade where no external services are required.

These verify early-validation behaviour that never reaches the network.
"""

from __future__ import annotations

import pytest

from nexora.config import Settings
from nexora.errors import UserInputError
from nexora.service import KnowledgeAssistant


def _assistant():
    # Constructing the assistant is lazy: no socket is opened until a query or
    # write actually runs, so default settings are safe to build offline.
    return KnowledgeAssistant(Settings())


def test_ingest_rejects_empty_document():
    with pytest.raises(UserInputError):
        _assistant().ingest_document("   ", "some label")


def test_ingest_rejects_very_short_document():
    with pytest.raises(UserInputError):
        _assistant().ingest_document("way too short", "some label")


def test_ask_question_rejects_blank_question():
    with pytest.raises(UserInputError):
        _assistant().ask_question("   ")
