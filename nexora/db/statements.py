"""Cypher statements used by the Nexora repository.

Every query lives in this module so the graph schema stays explicit and no
Cypher leaks into the service or UI layers.  Parameters use ``$name``
placeholders exclusively; the only interpolated value is the variable-length
depth bound in :func:`expansion_query`, which Cypher refuses to parameterise,
so it is validated to an integer before being embedded.
"""

from __future__ import annotations

# Graph schema ----------------------------------------------------------------
NODE_LABEL = "Entity"
REL_LABEL = "RELATED_TO"
DOC_LABEL = "Document"
MENTION_LABEL = "MENTIONED_IN"

# Entity upsert ---------------------------------------------------------------
# MERGE on the stable derived key; later sources enrich the same node and link
# it to their Document node via a MENTIONED_IN edge, preserving provenance
# across documents that mention the same entity.
UPSERT_ENTITY = f"""
MERGE (entity:{NODE_LABEL} {{ entity_id: $entity_id }})
ON CREATE SET entity.created_at = datetime()
SET entity.name = $name,
    entity.kind = $kind,
    entity.summary = $summary,
    entity.doc_ref = $doc_label,
    entity.excerpt = $excerpt
WITH entity
MERGE (doc:{DOC_LABEL} {{ label: $doc_label }})
WITH entity, doc
MERGE (entity)-[:{MENTION_LABEL}]->(doc)
"""

# Document upsert -------------------------------------------------------------
# Tracks the raw source text and first-seen timestamp for provenance/auditing.
# Re-ingesting under the same label refreshes the stored text.
UPSERT_DOCUMENT = f"""
MERGE (doc:{DOC_LABEL} {{ label: $label }})
ON CREATE SET doc.ingested_at = datetime()
SET doc.text = $text
RETURN doc.label AS label
"""

# Relation upsert --------------------------------------------------------------
# The OPTIONAL MATCH + WHERE pattern guarantees the link is only created when
# both endpoints already exist, so a sloppy extractor cannot manufacture
# empty placeholder nodes.
UPSERT_RELATION = f"""
MATCH (subject:{NODE_LABEL} {{ entity_id: $subject_id }})
OPTIONAL MATCH (object:{NODE_LABEL} {{ entity_id: $object_id }})
WITH subject, object
WHERE object IS NOT NULL
MERGE (subject)-[rel:{REL_LABEL} {{ kind: $kind }}]->(object)
SET rel.rationale = $rationale,
    rel.doc_ref = $doc_label
RETURN count(rel) AS linked
"""

# Retrieval --------------------------------------------------------------------
# Entry-point search: a node is a candidate when any question keyword shows
# up inside its name, category or summary text. Candidates are scored by how
# many distinct terms they match and ranked before the LIMIT is applied, so
# the most relevant seeds are never cut off by an alphabetical truncation.
SEARCH_ENTRY_POINTS = f"""
MATCH (entity:{NODE_LABEL})
WITH entity, [
    term IN $terms
    WHERE toLower(entity.name) CONTAINS term
       OR toLower(entity.kind) CONTAINS term
       OR toLower(entity.summary) CONTAINS term
] AS matched_terms
WHERE size(matched_terms) > 0
RETURN entity.entity_id AS entity_id,
       entity.name AS name,
       entity.kind AS kind,
       entity.summary AS summary,
       entity.doc_ref AS doc_label,
       entity.excerpt AS excerpt,
       size(matched_terms) AS score
ORDER BY score DESC, entity.name, entity.entity_id
LIMIT $limit
"""


def expansion_query(depth: int) -> str:
    """Return the multi-hop neighbourhood walk for a validated ``depth``."""
    if not isinstance(depth, int) or depth < 1:
        depth = 2
    return f"""
MATCH route = (seed:{NODE_LABEL})-[:{REL_LABEL}*1..{depth}]-(hop:{NODE_LABEL})
WHERE seed.entity_id = $seed_id
  AND NOT hop.entity_id = $seed_id
RETURN route
ORDER BY length(route), hop.name
LIMIT $window
"""


# Schema bootstrap -------------------------------------------------------------
# Optional.  Applied lazily and best-effort so graphs work even on databases
# where the application user lacks schema privileges.
SCHEMA_BOOTSTRAP = (
    f"CREATE CONSTRAINT nexora_entity_id IF NOT EXISTS "
    f"FOR (entity:{NODE_LABEL}) REQUIRE entity.entity_id IS UNIQUE",
    f"CREATE CONSTRAINT nexora_document_label IF NOT EXISTS "
    f"FOR (doc:{DOC_LABEL}) REQUIRE doc.label IS UNIQUE",
)

# Housekeeping ----------------------------------------------------------------
COUNT_NODES = f"MATCH (entity:{NODE_LABEL}) RETURN count(entity) AS total"
COUNT_EDGES = f"MATCH (:{NODE_LABEL})-[rel:{REL_LABEL}]->() RETURN count(rel) AS total"
COUNT_DOCUMENTS = f"MATCH (doc:{DOC_LABEL}) RETURN count(doc) AS total"
DISTINCT_SOURCES = (
    f"MATCH (doc:{DOC_LABEL}) RETURN collect(DISTINCT doc.label) AS labels"
)
# Only nodes that belong to Nexora's own schema are erased, so a shared or
# mixed-use database is never collateral damage.
WIPE_GRAPH = (
    f"MATCH (node) WHERE node:{NODE_LABEL} OR node:{DOC_LABEL} DETACH DELETE node"
)
