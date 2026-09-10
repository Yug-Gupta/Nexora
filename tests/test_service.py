"""Tests for the service facade where no external services are required.

These verify early-validation behaviour and health-report logic that never
reach the network (infrastructure objects are faked).
"""

from __future__ import annotations

import pytest
from nexora.config import Settings
from nexora.errors import UserInputError
from nexora.service import KnowledgeAssistant


@pytest.fixture
def assistant():
    # Constructing the assistant is lazy: no socket is opened until a query or
    # write actually runs, so default settings are safe to build offline. The
    # context manager guarantees the Neo4j driver is released on teardown.
    with KnowledgeAssistant(Settings()) as service:
        yield service


def test_ingest_rejects_empty_document(assistant):
    with pytest.raises(UserInputError):
        assistant.ingest_document("   ", "some label")


def test_ingest_rejects_very_short_document(assistant):
    with pytest.raises(UserInputError):
        assistant.ingest_document("way too short", "some label")


def test_ask_question_rejects_blank_question(assistant):
    with pytest.raises(UserInputError):
        assistant.ask_question("   ")


# --- health report -----------------------------------------------------------


class _OkConnector:
    def ping(self) -> None:
        pass


class _DownConnector:
    def ping(self) -> None:
        raise ConnectionError("connection refused")


class _Gateway:
    """Records how often the model list is fetched from the Gemini API."""

    def __init__(self, available, default_model="gemini-2.5-flash"):
        self._available = available
        self.default_model = default_model
        self.list_calls = 0

    @staticmethod
    def _norm(name):
        text = (name or "").strip()
        return text[len("models/") :] if text.startswith("models/") else text

    def available_models(self):
        self.list_calls += 1
        return list(self._available)

    def model_is_installed(self, model_name=None, *, installed=None):
        wanted = self._norm(model_name or self.default_model)
        return any(
            self._norm(name) == wanted for name in (installed or self._available)
        )


def _assistant_with(connector, gateway) -> KnowledgeAssistant:
    service = KnowledgeAssistant(Settings())
    service._connector.close()  # noqa: SLF001 - release the real (unused) driver
    service._connector = connector  # noqa: SLF001 - deliberate test seam
    service._gateway = gateway  # noqa: SLF001
    return service


def test_health_report_reports_all_services_healthy(assistant):
    service = _assistant_with(_OkConnector(), _Gateway(["gemini-2.5-flash"]))
    probes = service.health_report()
    by_name = {probe.component: probe for probe in probes}
    assert set(by_name) == {"Graph database", "Gemini API", "Configured model"}
    assert all(probe.available for probe in probes)
    assert "Ready." in by_name["Configured model"].message


def test_health_report_fetches_model_list_exactly_once():
    gateway = _Gateway(["models/gemini-2.5-flash"])
    service = _assistant_with(_OkConnector(), gateway)
    service.health_report()
    assert gateway.list_calls == 1


def test_health_report_reports_model_missing_when_unavailable():
    gateway = _Gateway(["gemini-2.0-flash"], default_model="gemini-2.5-flash")
    service = _assistant_with(_OkConnector(), gateway)
    probes = service.health_report()
    model = next(p for p in probes if p.component == "Configured model")
    assert model.available is False
    assert "not available" in model.message


def test_health_report_handles_graph_database_outage():
    service = _assistant_with(_DownConnector(), _Gateway(["gemini-2.5-flash"]))
    probes = service.health_report()
    graph = next(p for p in probes if p.component == "Graph database")
    assert graph.available is False
    assert graph.message


def test_health_report_handles_model_service_outage():
    class _Broken:
        default_model = "gemini-2.5-flash"

        def available_models(self):
            raise ConnectionError("connection refused")

    service = _assistant_with(_OkConnector(), _Broken())
    probes = service.health_report()
    gemini = next(p for p in probes if p.component == "Gemini API")
    configured = next(p for p in probes if p.component == "Configured model")
    assert gemini.available is False
    assert configured.available is False
