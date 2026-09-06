"""Turn a plain-text document into entities and relations via the local model."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from verigraph.errors import InferenceError, SourceError
from verigraph.llm.gateway import InferenceGateway
from verigraph.llm.prompts import build_extraction_prompt
from verigraph.models import Entity, Relation, truncate

logger = logging.getLogger(__name__)

_DEFAULT_KIND = "CONCEPT"
_EXCERPT_LIMIT = 300


def _locate_json_payload(raw: str) -> str:
    """Recover a JSON object from model output that may include prose/fences."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("No JSON object found in the model reply.")
    return text[start : end + 1]


def _parse_model_object(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(_locate_json_payload(raw))
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Model returned malformed JSON: %s", exc)
        raise SourceError(
            "The model did not return a usable structured result.",
            detail=f"malformed JSON: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise SourceError(
            "The model result was not an object with entity and relation arrays.",
            detail="unexpected JSON shape",
        )
    return payload


def _clean_text(value: Any, fallback: str = "") -> str:
    if not isinstance(value, str):
        return fallback
    return re.sub(r"\s+", " ", value).strip()


def _parse_entities(
    payload: dict[str, Any],
    source_label: str,
    document_text: str,
) -> list[Entity]:
    raw_entities = payload.get("entities", payload.get("nodes", []))
    entities: list[Entity] = []
    seen: set[str] = set()
    if not isinstance(raw_entities, list):
        raw_entities = []
    for item in raw_entities:
        if not isinstance(item, dict):
            continue
        name = _clean_text(item.get("name"))
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        entities.append(
            Entity(
                name=name,
                kind=_clean_text(item.get("type"), _DEFAULT_KIND).upper()
                or _DEFAULT_KIND,
                summary=_clean_text(item.get("summary")),
                source_label=source_label,
                excerpt=truncate(document_text, _EXCERPT_LIMIT),
            )
        )
    return entities


def _parse_relations(
    payload: dict[str, Any],
    source_label: str,
    known_names: set[str],
) -> list[Relation]:
    raw_relations = payload.get("relations", payload.get("edges", []))
    relations: list[Relation] = []
    if not isinstance(raw_relations, list):
        raw_relations = []
    for item in raw_relations:
        if not isinstance(item, dict):
            continue
        subject = _clean_text(item.get("source"))
        object_ = _clean_text(item.get("target"))
        predicate = _clean_text(item.get("type", "MENTIONS")).upper()
        if not subject or not object_ or subject.casefold() == object_.casefold():
            continue
        if subject.casefold() not in known_names or object_.casefold() not in known_names:
            logger.debug("Ignoring relation with unmatched endpoint %r -> %r", subject, object_)
            continue
        relations.append(
            Relation(
                subject=subject,
                object=object_,
                predicate=predicate or "MENTIONS",
                rationale=_clean_text(item.get("context")),
                source_label=source_label,
            )
        )
    return relations


def extract_graph_elements(
    document_text: str,
    source_label: str,
    gateway: InferenceGateway,
    model_name: str | None = None,
) -> tuple[list[Entity], list[Relation]]:
    """Ask the local model to structure a document, then validate the result."""
    prompt = build_extraction_prompt(document_text)
    try:
        reply = gateway.complete(prompt, model_name=model_name, expect_json=True)
    except InferenceError as exc:
        raise SourceError(
            "The language model could not analyse this document.",
            detail=exc.detail or str(exc),
        ) from exc

    payload = _parse_model_object(reply)
    entities = _parse_entities(payload, source_label, document_text)
    known = {entity.name.casefold() for entity in entities}
    relations = _parse_relations(payload, source_label, known)

    if not entities:
        raise SourceError(
            "No entities could be extracted from this document. "
            "Try shorter, clearly-written text.",
        )
    logger.info(
        "Extracted %d entities and %d relations from %r",
        len(entities),
        len(relations),
        source_label,
    )
    return entities, relations
