"""Turn a plain-text document into entities and relations via the local model.

The module is deliberately defensive: small local models do not always emit
clean JSON, sometimes use different field names, occasionally duplicate
entities and frequently reference relation endpoints that were never listed.
Every one of those failure modes is normalised or rejected here.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from nexora.errors import InferenceError, SourceError
from nexora.llm.gateway import InferenceGateway
from nexora.llm.prompts import build_extraction_prompt
from nexora.models import Entity, Relation, truncate

logger = logging.getLogger(__name__)

_DEFAULT_KIND = "CONCEPT"
_EXCERPT_LIMIT = 300
_MAX_ENTITY_NAME_LENGTH = 120
_MAX_PREDICATE_LENGTH = 60
_MAX_ENTITIES = 200
_MAX_RELATIONS = 400

_ENTITY_NAME_KEYS = ("name", "label")
_ENTITY_TYPE_KEYS = ("type", "kind", "category")
_ENTITY_SUMMARY_KEYS = ("summary", "description")
_REL_SUBJECT_KEYS = ("source", "subject", "from", "head")
_REL_OBJECT_KEYS = ("target", "object", "to", "tail")
_REL_PREDICATE_KEYS = ("type", "predicate", "relation", "label")
_REL_CONTEXT_KEYS = ("context", "rationale", "reason")


def _first_present(item: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


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
        name = _first_present(item, _ENTITY_NAME_KEYS)
        if not name:
            continue
        if len(name) > _MAX_ENTITY_NAME_LENGTH:
            logger.debug(
                "Dropping entity name longer than %d chars", _MAX_ENTITY_NAME_LENGTH
            )
            continue
        if name.casefold() in seen:
            continue
        seen.add(name.casefold())
        kind = _first_present(item, _ENTITY_TYPE_KEYS).upper() or _DEFAULT_KIND
        entities.append(
            Entity(
                name=name,
                kind=kind,
                summary=_first_present(item, _ENTITY_SUMMARY_KEYS),
                source_label=source_label,
                excerpt=truncate(document_text, _EXCERPT_LIMIT),
            )
        )
        if len(entities) >= _MAX_ENTITIES:
            break
    return entities


def _parse_relations(
    payload: dict[str, Any],
    source_label: str,
    known_names: set[str],
) -> list[Relation]:
    raw_relations = payload.get("relations", payload.get("edges", []))
    relations: list[Relation] = []
    seen: set[tuple[str, str, str]] = set()
    if not isinstance(raw_relations, list):
        raw_relations = []
    for item in raw_relations:
        if not isinstance(item, dict):
            continue
        subject = _first_present(item, _REL_SUBJECT_KEYS)
        object_ = _first_present(item, _REL_OBJECT_KEYS)
        predicate = _first_present(item, _REL_PREDICATE_KEYS).upper()
        if not predicate or len(predicate) > _MAX_PREDICATE_LENGTH:
            predicate = "MENTIONS"
        if not subject or not object_ or subject.casefold() == object_.casefold():
            continue
        if (
            subject.casefold() not in known_names
            or object_.casefold() not in known_names
        ):
            logger.debug(
                "Ignoring relation with unmatched endpoint %r -> %r",
                subject,
                object_,
            )
            continue
        dedupe_key = (subject.casefold(), predicate, object_.casefold())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        relations.append(
            Relation(
                subject=subject,
                object=object_,
                predicate=predicate,
                rationale=_first_present(item, _REL_CONTEXT_KEYS),
                source_label=source_label,
            )
        )
        if len(relations) >= _MAX_RELATIONS:
            break
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
