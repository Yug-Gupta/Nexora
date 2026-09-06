"""Application facade used by the presentation layer.

:class:`KnowledgeAssistant` owns the graph connector and the model gateway
and wires them to the extraction / retrieval / answering pipeline.  The UI
never manipulates Neo4j or Ollama directly, and every failure surfaces as
an :class:`~verigraph.errors.AppError` subclass with a UI-safe message.
"""

from __future__ import annotations

import logging

from verigraph.config import Settings
from verigraph.db.connector import Neo4jConnector
from verigraph.db.repository import KnowledgeBase
from verigraph.errors import UserInputError
from verigraph.llm.gateway import InferenceGateway
from verigraph.pipeline.answering import synthesise_answer
from verigraph.pipeline.extraction import extract_graph_elements
from verigraph.pipeline.retrieval import collect_context
from verigraph.models import (
    HealthProbe,
    IngestReport,
    QueryAnswer,
    StoreOverview,
)

logger = logging.getLogger(__name__)

_MIN_DOCUMENT_CHARS = 20


class KnowledgeAssistant:
    """High-level entry point that satisfies document and query workflows."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._connector = Neo4jConnector(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
            database=settings.neo4j_database,
        )
        self._store = KnowledgeBase(self._connector)
        self._gateway = InferenceGateway(
            base_url=settings.ollama_url,
            default_model=settings.model_name,
        )
        logger.info("KnowledgeAssistant ready (model=%s)", settings.model_name)

    # -- workflows -------------------------------------------------------------

    def ingest_document(self, document_text: str, source_label: str) -> IngestReport:
        """Extract a structure from ``document_text`` and persist it."""
        content = (document_text or "").strip()
        label = (source_label or "").strip()
        if len(content) < _MIN_DOCUMENT_CHARS:
            raise UserInputError(
                "The source text is too short to analyse. Paste at least a "
                "few meaningful sentences."
            )
        if not label:
            raise UserInputError("Please give the document a reference label.")

        entities, relations = extract_graph_elements(
            document_text=content,
            source_label=label,
            gateway=self._gateway,
            model_name=self.settings.model_name,
        )
        for entity in entities:
            self._store.save_entity(entity)
        dropped = 0
        for relation in relations:
            if not self._store.save_relation(relation):
                dropped += 1
        return IngestReport(
            source_label=label,
            entity_count=len(entities),
            relation_count=len(relations),
            dropped_relations=dropped,
            entities=tuple(entities),
            relations=tuple(relations),
        )

    def ask_question(self, question: str) -> QueryAnswer:
        """Run retrieval plus grounded generation for one natural-language query."""
        question = (question or "").strip()
        if not question:
            raise UserInputError("Please type a question first.")

        pieces, _, audit = collect_context(
            question=question,
            store=self._store,
            settings=self.settings,
        )
        answer_text, references = synthesise_answer(
            question=question,
            pieces=pieces,
            gateway=self._gateway,
            model_name=self.settings.model_name,
        )
        audit.append(
            f"Answer relies on {len(references)} verified source reference(s)."
        )
        return QueryAnswer(text=answer_text, references=references, audit=tuple(audit))

    # -- inspection --------------------------------------------------------------

    def overview(self) -> StoreOverview:
        """Return current graph size and the documents already indexed."""
        return self._store.overview()

    def health_report(self) -> tuple[HealthProbe, ...]:
        """Probe Neo4j, Ollama and the configured model without throwing."""
        probes: list[HealthProbe] = []

        try:
            self._connector.ping()
            probes.append(
                HealthProbe(
                    component="Graph database",
                    available=True,
                    message="Connected and responding.",
                )
            )
        except Exception as exc:
            probes.append(
                HealthProbe(
                    component="Graph database",
                    available=False,
                    message=str(exc),
                )
            )

        try:
            installed = self._gateway.available_models()
            probes.append(
                HealthProbe(
                    component="Model service",
                    available=True,
                    message=f"{len(installed)} model(s) available.",
                    extra=tuple(installed),
                )
            )
        except Exception as exc:
            probes.append(
                HealthProbe(
                    component="Model service",
                    available=False,
                    message=str(exc),
                )
            )

        try:
            probes.append(
                HealthProbe(
                    component="Configured model",
                    available=self._gateway.model_is_installed(),
                    message=(
                        "Ready."
                        if self._gateway.model_is_installed()
                        else f"'{self.settings.model_name}' not installed."
                    ),
                )
            )
        except Exception:
            probes.append(
                HealthProbe(
                    component="Configured model",
                    available=False,
                    message="Unknown until the model service responds.",
                )
            )
        return tuple(probes)

    def reset_graph(self) -> None:
        """Erase all data currently held in Neo4j."""
        self._store.wipe()

    def close(self) -> None:
        """Release the database connection."""
        self._connector.close()
        logger.info("KnowledgeAssistant closed")

    def __enter__(self) -> "KnowledgeAssistant":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
