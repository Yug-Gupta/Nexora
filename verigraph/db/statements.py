"""Cypher statements used by the repository.

Keeping every query in one module makes the graph schema explicit and
prevents Cypher from leaking into the UI or service layers.  Parameters
use ``$name`` placeholders exclusively; the single exception is the
variable-length depth bound, which Cypher refuses to parameterise, so
it is interpolated by :func:`expansion_query` after integer validation.
"""

from __future__ import annotations

NODE_LABEL = "Entity"
REL_LABEL = "RELATED_TO"

# Entity upsert ---------------------------------------------------------------
# MERGE on the stable derived key; later sources simply enrich the node.
UPSERT_ENTITY = f"""
MERGE (entity:{NODE_LABEL} {{ entity_id: $entity_id }})
SET entity.name = $name,
    entity.kind = $kind,
    entity.summary = $summary,
    entity.doc_ref = $doc_label,
    entity.excerpt = $excerpt
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
# up inside its name, category or summary text.
SEARCH_ENTRY_POINTS = f"""
MATCH (entity:{NODE_LABEL})
WHERE any(
    term IN $terms
    WHERE toLower(entity.name) CONTAINS term
       OR toLower(entity.kind) CONTAINS term
       OR toLower(entity.summary) CONTAINS term
)
RETURN entity.entity_id AS entity_id,
       entity.name AS name,
       entity.kind AS kind,
       entity.summary AS summary,
       entity.doc_ref AS doc_label,
       entity.excerpt AS excerpt
ORDER BY entity.name
LIMIT $limit
"""


def expansion_query(depth: int) -> str:
    """Return the multi-hop neighborhood walk for a validated ``depth``."""
    if not isinstance(depth, int) or depth < 1:
        depth = 2
    return f"""
MATCH route = (seed:{NODE_LABEL})-[:{REL_LABEL}*1..{depth}]-(hop:{NODE_LABEL})
WHERE seed.entity_id = $seed_id
  AND NOT hop.entity_id = $seed_id
RETURN route
LIMIT $window
"""

# Housekeeping ----------------------------------------------------------------
COUNT_NODES = f"MATCH (entity:{NODE_LABEL}) RETURN count(entity) AS total"
COUNT_EDGES = (
    f"MATCH (:Entity)-[rel:{REL_LABEL}]->() RETURN count(rel) AS total"
)
DISTINCT_SOURCES = (
    f"MATCH (entity:{NODE_LABEL}) "
    "RETURN collect(DISTINCT entity.doc_ref) AS labels"
)
WIPE_GRAPH = "MATCH (node) DETACH DELETE node"
