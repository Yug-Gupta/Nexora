# Nexora — Complete Project Guide

**Nexora · Knowledge Graph Intelligence Engine**

This document is the complete technical handbook for Nexora. It is written for
the project owner/developer (not end users) and is intentionally far more
detailed than the public `README.md`. Keep it with the repository: if you can
only open one file to understand this project, open this one.

> Every statement below was verified against the code in this repository. If
> you change the code, update this document in the same commit.

---

## 1. Project Identity

| Field | Value |
| --- | --- |
| Name | Nexora |
| Product tagline | Knowledge Graph Intelligence Engine |
| Python package | `nexora` |
| App entry point | `app.py` (Streamlit) |
| Purpose | GraphRAG over your own documents with the Google Gemini API |
| Main capabilities | Document ingestion, entity/relation extraction, Neo4j knowledge graph, multi-hop retrieval, grounded answer generation, provenance/citations, live diagnostics |
| Technology stack | Python 3.10+, Streamlit, Neo4j (official driver), Google Gemini (`google-genai`), Docker Compose (optional), pytest, ruff |

The package identity constants live in `nexora/__init__.py`:

```python
__version__ = "1.0.0"
__app_name__ = "Nexora"
__tagline__ = "Knowledge Graph Intelligence Engine"
```

---

## 2. What Nexora Does

In plain language:

1. You paste a piece of text (a paragraph about a company, an event, a product
   ecosystem…) and give it a reference label.
2. Nexora asks the **Google Gemini API** to read the text and return a
   structured JSON description of the *entities* it mentions and the
   *relationships* between them.
3. Nexora validates that JSON (LLMs are imperfect), then writes it into a
   **Neo4j knowledge graph**. The same entity mentioned in several documents
   becomes one shared node, and each document is recorded as a provenance
   node.
4. Later, you ask a natural-language question. Nexora turns it into search
   keywords, finds matching *seed* entities, and **walks the graph** a few
   relationship hops to collect connected evidence (this is what lets it join
   facts that live in different documents).
5. The collected evidence is handed to Gemini as numbered entries with an
   instruction to ground every claim in one or more entries and cite them
   inline as `[1]`, `[2]`.
6. Nexora parses those citations, verifies each one against the real evidence,
   and renders the answer with expandable source cards showing the document,
   an excerpt and the graph route used to reach each piece of evidence.

The knowledge graph lives in your Neo4j database; document text and questions
are sent to the Google Gemini API for extraction and answering.

---

## 3. High-Level Architecture

Nexora is split into a **core engine** (`nexora`) and a **Streamlit
presentation layer** (`nexora/ui`). The engine never imports Streamlit; the UI
never runs Cypher or builds prompts. They meet at one facade class:
`nexora.service.KnowledgeAssistant`.

```
┌──────────── nexora/ (engine — no Streamlit) ─────────────┐
│                                                           │
│  config.Settings          every tunable, .env loading     │
│  errors.AppError family   typed, UI-safe failures         │
│  models.*                frozen domain records            │
│                                                           │
│  db/    connector.py   Neo4j driver lifecycle             │
│         statements.py  all Cypher + graph schema          │
│         repository.py  KnowledgeBase (read/write)         │
│                                                           │
│  llm/   gateway.py     InferenceGateway (Gemini client)   │
│         prompts.py     extraction + answering templates    │
│                                                           │
│  pipeline/ extraction.py  text -> validated entities/rels │
│           retrieval.py    question -> context + routes     │
│           answering.py    context -> answer + citations    │
│                                                           │
│  service.KnowledgeAssistant  facade wiring the above      │
└───────────────────────────────────────────────────────────┘
                          ▲ delegates
┌─────────────────────────┴──────────────────────────────────┐
│  app.py (root)  -> nexora.ui.main()                        │
│  nexora/ui/  theme, state, sidebar, ingest_view,           │
│              ask_view, status_view  (the only Streamlit)   │
└────────────────────────────────────────────────────────────┘
```

Design rules enforced in this codebase:

- Only `nexora/db/connector.py` touches `neo4j.GraphDatabase.driver`.
- Only `nexora/llm/gateway.py` imports `google-genai`.
- Only `nexora/ui/**` imports `streamlit`; `nexora/ui/state.py` bridges
  Streamlit secrets into the environment so the engine stays Streamlit-free.
- Every Cypher query lives in `nexora/db/statements.py`.
- Every prompt lives in `nexora/llm/prompts.py`.
- No engine module reaches into `os.environ` except `nexora/config.py`.
- All user-facing errors derive from `nexora.errors.AppError` and carry a
  UI-safe `message` plus a technical `detail` intended for logs.
- The Gemini API key is never logged, displayed or embedded in error details.

---

## 4. Complete Data Flow

```
 Document (text + label)
   │
   ▼ 1. service.KnowledgeAssistant.ingest_document()
 extract_graph_elements()
   │  builds extraction prompt (prompts.build_extraction_prompt)
   │  gateway.complete(..., expect_json=True)   [Gemini]
   │  JSON payload → validate & normalise        (extraction.py)
   ▼ entities: list[Entity], relations: list[Relation]
 store.register_document(label, text)            (Document node)
 for entity:  store.save_entity(entity)          (Entity node + MENTIONED_IN)
 for relation: store.save_relation(relation)     (RELATED_TO if endpoints exist)
   ▼
 IngestReport → UI tables
   ▼ (later)
 User question
   │
   ▼ 2. service.KnowledgeAssistant.ask_question()
 collect_context()
   │  derive_terms(question)            → keywords
   │  store.locate_entry_points(terms)  → seed rows
   │  rank seeds by matched keywords    → top 3 seeds
   │  for each seed: store.grow_neighbourhood(seed, depth) → rows + routes
   ▼ context: list[ContextPiece]   (+ audit lines)
 synthesise_answer()
   │  build_answer_prompt(question, pieces)
   │  gateway.complete(...)                            [Gemini]
   │  parse & verify inline citations  → references
   ▼
 QueryAnswer(text, references, audit) → UI answer card + source cards
```

Provenance is tracked end-to-end: `Relation.rationale`, per-node `doc_ref`,
per-document `Document` nodes, route strings on every `ContextPiece`, and
verified `ProvenanceRecord`s on every `QueryAnswer`.

---

## 5. Repository Structure

```
.
├── app.py                        # Streamlit bootstrap
├── nexora/                       # core engine package
│   ├── __init__.py               # package metadata (version, brand)
│   ├── config.py
│   ├── errors.py
│   ├── models.py
│   ├── samples.py
│   ├── service.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connector.py
│   │   ├── statements.py
│   │   └── repository.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── gateway.py
│   │   └── prompts.py
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── extraction.py
│   │   ├── retrieval.py
│   │   └── answering.py
│   └── ui/
│       ├── __init__.py           # main(): page config + tabs
│       ├── theme.py              # brand palette, CSS, HTML helpers
│       ├── state.py              # session-state + error presenter
│       ├── sidebar.py            # connection settings + overrides
│       ├── ingest_view.py        # ingestion tab
│       ├── ask_view.py           # answering tab
│       └── status_view.py        # diagnostics / overview / danger zone
├── tests/
│   ├── test_config.py
│   ├── test_models.py
│   ├── test_extraction.py
│   ├── test_retrieval.py
│   ├── test_answering.py
│   ├── test_llm.py
│   ├── test_service.py
│   └── test_ui_state.py
├── docs/
│   ├── NEXORA_PROJECT_GUIDE.md  # this document
│   └── DEPLOYMENT.md            # hosting a public live demo on a VPS
├── deploy/
│   └── Caddyfile                # HTTPS reverse proxy + Basic Auth
├── .github/workflows/ci.yml      # lint + test pipeline on push / PR
├── .dockerignore
├── .env.example
├── .gitignore
├── .gitattributes                # consistent line endings across platforms
├── .streamlit/config.toml
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml                # ruff + pytest configuration
├── Dockerfile
├── docker-compose.yml
├── docker-compose.prod.yml       # Caddy proxy overlay (used with the base)
├── CHANGELOG.md
├── SECURITY.md
└── LICENSE
```

### Module-by-module reference

#### `app.py` (root)
- **Purpose:** Streamlit entry point. Run with `streamlit run app.py`.
- **Responsibility:** imports `nexora.ui.main()` and calls it under
  `__main__`. It exists so the project can be launched by filename from the
  repo root.
- **Inputs/Outputs:** none of its own; delegates to the UI package.

#### `nexora/__init__.py`
- **Purpose:** package identity.
- **Exports:** `__version__`, `__app_name__`, `__tagline__`.

#### `nexora/config.py`
- **Purpose:** central configuration.
- **Responsibility:** reads environment variables plus an optional `.env` file
  at the repository root and exposes an immutable `Settings` dataclass. Also
  installs logging for the `nexora` logger tree (idempotent).
- **Important classes:** `Settings` (frozen dataclass).
- **Important functions:** `Settings.from_environment()` (process env wins over
  `.env`), `Settings.with_overrides(**changes)` (returns a new record),
  `Settings.signature()` (tuple used to detect connection changes),
  `configure_logging(level)`.
- **Inputs:** process environment / `.env`.
- **Outputs:** `Settings` records.
- **Dependencies:** stdlib only.
- **Notes:** parsing helpers `_as_int`/`_as_float` clamp values into sane
  ranges so a typo in `.env` can never produce depth 99 or a negative timeout.

#### `nexora/errors.py`
- **Purpose:** typed error taxonomy.
- **Responsibility:** all application-raised errors derive from `AppError`,
  which stores a UI-safe `message` and a technical `detail`.
- **Classes:** `AppError`, `UserInputError`, `StorageError`, `InferenceError`,
  `SourceError`, `ContextError`.
- **Functions:** `translate_storage_failure(exc)`, `translate_inference_failure(exc)`
  map driver/SDK exceptions onto friendly `StorageError`/`InferenceError`s.
- **Dependencies:** stdlib (driver imports are lazy inside the translators so
  the module imports even without Neo4j installed).

#### `nexora/models.py`
- **Purpose:** the vocabulary of the pipeline.
- **Classes:** `Entity`, `Relation`, `ContextPiece`, `ProvenanceRecord`,
  `QueryAnswer`, `IngestReport`, `StoreOverview`, `HealthProbe`.
- **Functions:** `entity_identifier(name)` (stable key: `ent:` + first 16 hex
  chars of the SHA-256 of the case-folded, whitespace-normalised name),
  `truncate(text, limit=280)`.
- **Dependencies:** stdlib.
- **Notes:** `StoreOverview` carries `node_count`, `edge_count`,
  `document_count`, `sources`. All records are frozen dataclasses.

#### `nexora/samples.py`
- **Purpose:** demo content.
- **Exports:** `SAMPLE_DOCUMENTS` (three passages intentionally sharing
  entities), `SUGGESTED_QUESTIONS` (four questions that require joining facts
  across documents).

#### `nexora/service.py`
- **Purpose:** facade for the UI.
- **Responsibility:** owns a `Neo4jConnector`, a `KnowledgeBase`, an
  `InferenceGateway`; exposes high-level workflows.
- **Class:** `KnowledgeAssistant(settings)`.
- **Methods:**
  - `ingest_document(document_text, source_label) -> IngestReport`
  - `ask_question(question) -> QueryAnswer`
  - `overview() -> StoreOverview`
  - `health_report() -> tuple[HealthProbe, ...]`
  - `reset_graph() -> None`
  - `close()` / context-manager support
- **Inputs:** `Settings`; validated user text/questions.
- **Outputs:** domain records; raises `AppError` subclasses.
- **Dependencies:** db + llm + pipeline layers.
- **Notes:** enforces `_MIN_DOCUMENT_CHARS = 20`; registers the document before
  saving entities so provenance exists even for relation-less documents.
  `health_report()` fetches the available-model list exactly once and reuses it
  for both the *Gemini API* and the *Configured model* probes, so a health
  check never issues two redundant `models.list` calls.

#### `nexora/db/__init__.py`
Docstring-only marker.

#### `nexora/db/connector.py`
- **Purpose:** ownership of the Neo4j driver.
- **Responsibility:** the *only* module using `neo4j.GraphDatabase.driver`.
  Construction is lazy (no socket until first query), so the app starts even
  when Neo4j is offline.
- **Class:** `Neo4jConnector(uri, user, password, database=None)`.
- **Methods:** `session()` (bound to the configured database when set),
  `ping()` (forces a trivial round-trip), `close()`.
- **Errors:** invalid URIs raise `StorageError`; unreachable/auth errors are
  translated via `translate_storage_failure`.
- **Dependencies:** `neo4j` driver.

#### `nexora/db/statements.py`
- **Purpose:** every Cypher statement and the graph schema, in one place.
- **Schema constants:** `Entity`, `RELATED_TO`, `Document`, `MENTIONED_IN`.
- **Statements:**
  - `UPSERT_ENTITY` — MERGE on `entity_id`; enrich; link to its Document node
    with `MENTIONED_IN`.
  - `UPSERT_DOCUMENT` — MERGE a Document by label; store text + first-seen
    timestamp.
  - `UPSERT_RELATION` — only creates `RELATED_TO` when both endpoints exist.
  - `SEARCH_ENTRY_POINTS` — keyword match over name/kind/summary, scored by
    the number of distinct terms matched and ranked **before** the `LIMIT`, so
    the most relevant seeds are never truncated alphabetically.
  - `expansion_query(depth)` — variable-length multi-hop walk (the only
    interpolated Cypher; depth is validated to an int first). Results are
    ordered by route length so the shortest route to each entity is seen first.
  - `SCHEMA_BOOTSTRAP` — optional uniqueness constraints.
  - `COUNT_NODES`, `COUNT_EDGES`, `COUNT_DOCUMENTS`, `DISTINCT_SOURCES`,
    `WIPE_GRAPH`.
- **Dependencies:** none (pure strings/functions).
- **Security:** every value is parameterised (`$name`); only the integer depth
  is embedded, after validation. `WIPE_GRAPH` deletes only `Entity` and
  `Document` nodes, never unrelated data in a shared database.

#### `nexora/db/repository.py`
- **Purpose:** graph read/write operations for the pipeline.
- **Class:** `KnowledgeBase(connection)`.
- **Methods:** `register_document`, `save_entity`, `save_relation` (returns
  `False` when an endpoint is missing), `locate_entry_points`,
  `grow_neighbourhood`, `overview`, `wipe`, plus helpers
  `_decompose_path`/`_route_labels` that turn Neo4j `Path` objects into
  `A --[pred]-- B` route strings.
- **Errors:** driver failures translated via `translate_storage_failure`.
- **Dependencies:** `nexora.db.statements`, `nexora.models`.
- **Notes:** `_ensure_schema()` runs once per instance, best-effort; constraint
  creation can be denied on managed databases, so failures are logged and
  ignored (MERGE still works without constraints).

#### `nexora/llm/__init__.py`
Docstring-only marker.

#### `nexora/llm/gateway.py`
- **Purpose:** sole wrapper around the Google Gemini API (`google-genai`).
- **Class:** `InferenceGateway(api_key, default_model, timeout_seconds=300,
  *, client=None)`. The optional `client` is a test seam; in production the
  real `genai.Client` is built lazily only when an API key is present.
- **Methods:** `is_configured()`, `available_models()` (calls
  `client.models.list()` and normalises `models/<name>` → `<name>`),
  `model_is_installed(model_name=None, *, installed=None)` (an already-fetched
  list may be passed in to avoid a second API round-trip), `complete(prompt,
  model_name=None, *, expect_json=False)`.
- **Extraction reliability:** `expect_json=True` sets Gemini's
  `response_mime_type="application/json"`, keeping entity/relation extraction
  as valid JSON.
- **Response parsing:** helper functions `_extract_response_text`,
  `_extract_model_names` and `_model_short_name` accept both typed SDK objects
  and plain dicts, so mocks and older SDK builds are supported.
- **Timeout:** forwarded as `HttpOptions(timeout=<ms>)`; falls back gracefully
  on SDK builds that do not accept it.
- **Errors:** invalid key, rate limits, server errors, network failures,
  timeouts and empty replies are translated via `translate_inference_failure`
  into `InferenceError`, without ever including the API key.

#### `nexora/llm/prompts.py`
- **Purpose:** prompt templates, isolated from logic.
- **Functions:** `build_extraction_prompt(content)`, `format_context_piece(index,
  piece)`, `build_answer_prompt(question, pieces)`.
- **Notes:** `ALLOWED_ENTITY_TYPES` documents the extraction categories
  (PERSON, ORGANIZATION, PRODUCT, TECHNOLOGY, LOCATION, EVENT, CONCEPT).

#### `nexora/pipeline/__init__.py`
Docstring-only marker.

#### `nexora/pipeline/extraction.py`
- **Purpose:** document → validated entities/relations.
- **Functions:** `extract_graph_elements(document_text, source_label, gateway,
  model_name=None)` and internal parsers.
- **Robustness:** strips JSON fences/prose (`_locate_json_payload`), accepts
  alternate field names (`label`/`kind`, `from`/`to`, …), de-duplicates
  entities case-insensitively, de-duplicates relations, drops blank/oversized
  names and self-loops, filters relations whose endpoints were never listed,
  caps entity/relation counts, defaults missing types to `CONCEPT`, and raises
  `SourceError` on unusable JSON or empty extraction.
- **Errors:** wraps `InferenceError` into `SourceError` with a user message.

#### `nexora/pipeline/retrieval.py`
- **Purpose:** question → ranked seeds → multi-hop context.
- **Functions:** `derive_terms(question)` (case-folded keywords, English
  stop-word list), `_rank_seeds(seeds, terms)` (by how many keywords each seed
  matches, ties alphabetical), `collect_context(...)`.
- **Constants:** `_MAX_SEEDS_PER_QUERY = 3` (top seeds expanded).
- **Errors:** `ContextError` when no terms, no seeds, or no connected context.
- **Outputs:** `(pieces, seed_names, audit)`; every piece may carry the graph
  `route` used to reach it.
- **Notes:** seed discovery already ranks matches in Cypher (see
  `SEARCH_ENTRY_POINTS`), so the pool fetched by `locate_entry_points` is the
  most relevant one, not an alphabetical slice. Neighbourhood expansion stops
  as soon as the context cap is reached — no needless extra queries.

#### `nexora/pipeline/answering.py`
- **Purpose:** evidence → answer + verified citations.
- **Functions:** `synthesise_answer(question, pieces, gateway, model_name=None)`,
  `_expand_cited_indices`, `_collect_references`.
- **Notes:** supports `[n]` and comma/space groups such as `[1, 3]`; only
  citations that resolve to a real entry survive; references sorted by index.
  An answer that simply omits citations is returned as-is (the UI explains
  that the model qualified or generalised).

#### `nexora/ui/**`
- `__init__.py`: `main()` — configures logging, sets the page config, renders
  hero + sidebar, then three tabs (Ingest knowledge / Ask a question / System
  status), each backed by a view module.
- `theme.py`: brand constants, page CSS, and tiny HTML helpers
  (`render_hero`, `render_metric_grid`, `status_pill`, `render_answer_card`,
  `render_answer_markup`). All model/user text is HTML-escaped before
  rendering.
- `state.py`: `current_settings`, `update_settings`, `reset_settings`,
  `get_assistant` (cached by settings signature, closes the previous assistant
  on change), overview/probes caching, `present_error`, and
  `hydrate_environment_from_secrets` — the bridge that copies whitelisted
  `st.secrets` values into the environment for Streamlit Community Cloud.
- `sidebar.py`: live connection form (Neo4j, Gemini API key + model, retrieval
  behaviour), save/reconnect, reset-to-defaults, service summary, about.
- `ingest_view.py`: sample picker, text editor, reference label, “Analyse and
  index” action, ingestion report (metrics + tables).
- `ask_view.py`: suggested questions, question editor, grounded-answer card,
  reasoning audit, expandable source evidence.
- `status_view.py`: diagnostics (probes), graph overview (metrics, indexed
  documents), danger zone (erase with confirmation).

---

## 6. Configuration Guide

All values below are read by `nexora/config.py`. Real environment variables
win over `.env`. Copy `.env.example` → `.env` and edit. On Streamlit Community
Cloud the same keys can be provided through `st.secrets` (see §24).

| Variable | Purpose | Required? | Example | Used in |
| --- | --- | --- | --- | --- |
| `GEMINI_API_KEY` | Google Gemini API key (**secret**) | **Yes** | `AIza…` (never commit) | `gateway.py` |
| `GEMINI_MODEL` | Gemini model for extraction + answering | No (default) | `gemini-2.5-flash` | `service.py`, `gateway.py` |
| `NEO4J_URI` | Neo4j Bolt URI (local or `neo4j+s://` AuraDB) | No (default) | `bolt://127.0.0.1:7687` | `connector.py` |
| `NEO4J_USER` | Neo4j user name | No (default) | `neo4j` | `connector.py` |
| `NEO4J_PASSWORD` | Neo4j password | **Yes** for a real DB | `change_me` | `connector.py` |
| `NEO4J_DATABASE` | Neo4j database; server default when empty | No | `neo4j` | `connector.py` |
| `NEXORA_RETRIEVAL_DEPTH` | Hops walked per seed (clamped 1–6) | No (default `2`) | `2` | `retrieval.py` |
| `NEXORA_ENTRY_LIMIT` | Max seed candidates returned (clamped 1–30) | No (default `8`) | `8` | `retrieval.py` |
| `NEXORA_CONTEXT_LIMIT` | Max evidence entries per prompt (clamped 4–60) | No (default `18`) | `18` | `retrieval.py` |
| `NEXORA_LLM_TIMEOUT` | Seconds per Gemini request (clamped 5–3600) | No (default `300`) | `300` | `gateway.py` |
| `NEXORA_LOG_LEVEL` | Log level for the `nexora` logger tree | No (default `INFO`) | `DEBUG` | `config.configure_logging` |

The sidebar of the running app can override the connection/model/retrieval
values for the current browser session (stored in Streamlit session state).
Nothing is written to `.env` by the UI.

---

## 7. Neo4j Guide

### Installation / Docker setup

Local (Docker):

```bash
docker run -d --name nexora-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

- Browser UI: `http://localhost:7474`
- Bolt (driver): `bolt://localhost:7687`

Or use the compose file (`docker compose up --build`) which starts Neo4j and
the app together (inference runs on the Gemini API, so there is no model
container).

### Neo4j AuraDB

To use a managed database instead of local Docker, set the values AuraDB
provides:

```
NEO4J_URI=neo4j+s://<your-instance-id>.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=<your-auradb-password>
```

The connector opens sessions against the configured URI/database, so no code
change is required.

### Credentials configuration

Put them in `.env` (never commit `.env`):

```
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

### Graph schema

Two node labels and two relationship types are used:

| Object | Label / Type | Notes |
| --- | --- | --- |
| Entity node | `Entity` | a typed concept |
| Document node | `Document` | provenance record of an ingested source |
| Relation edge | `RELATED_TO` | `(subject)-[:RELATED_TO {kind}]->(object)` |
| Provenance edge | `MENTIONED_IN` | `(entity)-[:MENTIONED_IN]->(document)` |

**Entity properties**

| Property | Meaning |
| --- | --- |
| `entity_id` | stable key `ent:<sha256(name)[:16]>` — merge target |
| `name` | display name (as written) |
| `kind` | type label (PERSON, ORGANIZATION, …) |
| `summary` | one-sentence description from extraction |
| `doc_ref` | label of the most recently ingested document that mentioned it |
| `excerpt` | truncated source text (≤300 chars) from `doc_ref` |
| `created_at` | set on first creation |

**Document properties**

| Property | Meaning |
| --- | --- |
| `label` | the user-supplied reference label (merge key) |
| `text` | raw source text (refreshed on re-ingest of the same label) |
| `ingested_at` | first-seen timestamp |

**RELATED_TO properties:** `kind` (predicate, e.g. `FOUNDED_BY`), `rationale`,
`doc_ref` (the document that asserted the relation).

### Important Cypher queries

```cypher
// Entity upsert by stable key, then link to its document
MERGE (e:Entity {entity_id: $entity_id})
ON CREATE SET e.created_at = datetime()
SET e.name = $name, e.kind = $kind, e.summary = $summary,
    e.doc_ref = $doc_label, e.excerpt = $excerpt
WITH e
MERGE (d:Document {label: $doc_label})
WITH e, d
MERGE (e)-[:MENTIONED_IN]->(d)

// Relationship only when both endpoints exist
MATCH (s:Entity {entity_id: $subject_id})
OPTIONAL MATCH (o:Entity {entity_id: $object_id})
WITH s, o WHERE o IS NOT NULL
MERGE (s)-[r:RELATED_TO {kind: $kind}]->(o)
SET r.rationale = $rationale, r.doc_ref = $doc_label
RETURN count(r) AS linked

// Multi-hop expansion (depth is an integer embedded by expansion_query);
// shortest routes are returned first so each entity is seen via its closest hop
MATCH route = (seed:Entity)-[:RELATED_TO*1..2]-(hop:Entity)
WHERE seed.entity_id = $seed_id AND NOT hop.entity_id = $seed_id
RETURN route
ORDER BY length(route), hop.name
LIMIT $window

// Keyword entry-point search — scored before the LIMIT so the pool holds the
// most relevant candidates rather than an alphabetical slice
MATCH (e:Entity)
WITH e, [term IN $terms
  WHERE toLower(e.name) CONTAINS term
     OR toLower(e.kind) CONTAINS term
     OR toLower(e.summary) CONTAINS term] AS matched_terms
WHERE size(matched_terms) > 0
RETURN e.entity_id AS entity_id, e.name AS name, ...,
       size(matched_terms) AS score
ORDER BY score DESC, e.name, e.entity_id
LIMIT $limit
```

### Indexes / constraints

The repository bootstraps the following automatically on first write
(best-effort — failures are logged and ignored so constrained/read-restricted
servers still work):

```cypher
CREATE CONSTRAINT nexora_entity_id IF NOT EXISTS
  FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE
CREATE CONSTRAINT nexora_document_label IF NOT EXISTS
  FOR (d:Document) REQUIRE d.label IS UNIQUE
```

MERGE works without them; they make it faster and safer.

### Troubleshooting (Neo4j)

| Symptom | Fix |
| --- | --- |
| App says “Could not reach the Neo4j server” | Start Neo4j; check `NEO4J_URI`/port; on Compose use `bolt://graphdb:7687`. |
| “Neo4j rejected the credentials” | Verify `NEO4J_USER`/`NEO4J_PASSWORD`; reset auth with `NEO4J_AUTH`. |
| First ingest fails with schema error | If the DB user lacks schema rights, Nexora logs “schema bootstrap skipped” and continues; MERGE needs no constraints. |
| Graph has stale/old-shape data after an upgrade | The app does not migrate existing graphs. Use “Erase the entire graph” on the System tab (it deletes only Nexora `Entity`/`Document` nodes) and re-ingest. |

---

## 8. Gemini Guide

### Get an API key and choose a model

1. Create an API key in **Google AI Studio**. Treat it as a secret.
2. Store it as `GEMINI_API_KEY` in `.env` (local) or in Streamlit secrets
   (Community Cloud). Never commit it, log it or paste it into code.
3. Choose a model with `GEMINI_MODEL` — the default is `gemini-2.5-flash`;
   `gemini-2.0-flash` also works.

### How Nexora talks to Gemini

- `nexora/llm/gateway.py` builds one `genai.Client(api_key=…,
  http_options=HttpOptions(timeout=<ms>))` per `KnowledgeAssistant`, and only
  when a key is present.
- Extraction calls `complete(..., expect_json=True)`, which sets
  `response_mime_type="application/json"` so the response is valid JSON.
- Answering calls `complete(..., expect_json=False)`.
- `available_models()` calls `client.models.list()` for health checks; the key
  is never returned or displayed.

### Troubleshooting (Gemini)

| Symptom | Fix |
| --- | --- |
| “The Gemini API key is not configured” | Set `GEMINI_API_KEY` in `.env`/secrets and restart. |
| “The Gemini API key was rejected” | The key is invalid or disabled — create a new one in AI Studio. |
| “rate limit was reached” | Free-tier quota hit; wait a moment or switch `GEMINI_MODEL`. |
| “took too long to answer” | Raise `NEXORA_LLM_TIMEOUT`; try a lighter model. |
| “model … not available” | Check the exact model name in `GEMINI_MODEL`. |
| Extraction returns unusable JSON repeatedly | Try a stronger model; the gateway already requests JSON mode. |

---

## 9. Installation Guide (fresh checkout)

```bash
# 1. Clone / open the repository
cd Nexora

# 2. Virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
# source .venv/bin/activate

# 3. Dependencies
pip install -r requirements.txt

# (development extra)
pip install -r requirements-dev.txt

# 4. Environment file
# Windows:
Copy-Item .env.example .env
# macOS / Linux:
# cp .env.example .env
# then edit .env with your real Neo4j password and model name.

# 5. Neo4j (Docker)
docker run -d --name nexora-neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest

# 6. Gemini API key
#    Set GEMINI_API_KEY (and optionally GEMINI_MODEL) in .env, or in
#    Streamlit secrets when deploying to Community Cloud.
```

---

## 10. Startup Guide (step-by-step)

1. Ensure Neo4j is reachable: `NEO4J_URI`, credentials in `.env` (or AuraDB).
2. Ensure `GEMINI_API_KEY` is set (and `GEMINI_MODEL` is a model your key can
   use).
3. From the repository root, with the venv active:

   ```bash
   streamlit run app.py
   ```

4. Open `http://localhost:8501`.
5. Check connectivity first: **System status → Run diagnostics**. You should
   see Neo4j Available, Gemini API Available, and your model Ready.
6. **Ingest knowledge** → load an example or paste text → *Analyse and index*.
7. **Ask a question** → pick/type a question → *Get grounded answer*.

---

## 11. Daily Development Workflow

- **Start services:** Neo4j (Docker container or Compose). No model service —
  inference is the Gemini API.
- **Run Nexora:** `streamlit run app.py` (Streamlit auto-reloads on save).
- **Run tests:** `python -m pytest` (or `python -m pytest -q`).
- **Lint / format:** `ruff check .` and `ruff format .`
- **Inspect logs:** the console running Streamlit prints `nexora` logger lines
  with timestamps (`configure_logging` installs one console handler).
- **Stop services:** `Ctrl+C` on Streamlit; `docker stop nexora-neo4j` for the
  DB.
- **Reset dev data:** System tab → *Erase the entire graph*. This deletes only
  Nexora’s own nodes (`Entity` and `Document`), so unrelated data in a shared
  database is left untouched.

---

## 12. Document Ingestion

When you submit a document from **Ingest knowledge**:

1. `KnowledgeAssistant.ingest_document` validates length ≥ 20 chars and a
   non-blank label (`UserInputError` otherwise).
2. `extract_graph_elements` calls the model for structured JSON.
3. `register_document(label, text)` upserts the `Document` node.
4. Entities are saved one by one (merged by `entity_id`, linked to the
   document).
5. Relations are saved only when both endpoints exist; skipped ones are counted
   in `IngestReport.dropped_relations`.
6. The UI shows metrics and two tables (entities/relationships).

---

## 13. Entity Extraction

- Prompt: `nexora/llm/prompts.py` → `build_extraction_prompt`.
- The model is asked for `entities[]` with `name`, `type` (from
  `ALLOWED_ENTITY_TYPES`), `summary`.
- Validation in `extraction.py`: JSON recovery from fences/prose; field aliases;
  case-insensitive de-duplication; name length cap (120); count caps (200
  entities / 400 relations); blank names dropped; missing type → `CONCEPT`.
- Empty extraction → `SourceError` (“No entities could be extracted…”).

## 14. Relationship Extraction

- Same prompt: `relations[]` with `source`, `target`, `type` (uppercase
  predicate), `context`.
- Validation: endpoints must exist in the extracted entity set (otherwise
  dropped with a debug log); self-loops dropped; duplicates dropped; empty
  predicate → `MENTIONS`.
- Persistence additionally requires both endpoints to exist in the **graph**
  (`save_relation` returns `False` otherwise).

## 15. Neo4j Storage

Entities and documents are stored with `MERGE` on stable keys. Relations with
`MERGE` guarded by endpoint existence. Retrieval, counts, source listing and
wipe are all parameterised queries from `nexora/db/statements.py`.

## 16. Retrieval

`collect_context(question, store, settings)`:

1. `derive_terms` — case-folded keywords, English stop-words removed, tokens
   ≥3 chars.
2. `store.locate_entry_points` — nodes whose name/kind/summary contain any
   keyword. The Cypher ranks matches by how many distinct terms each node hits
   **before** applying `LIMIT`, so the pool always holds the most relevant
   candidates.
3. `_rank_seeds` — sorts that pool by matched-keyword count (ties alphabetical)
   and the top `_MAX_SEEDS_PER_QUERY` (3) seeds are expanded.
4. `store.grow_neighbourhood(seed, retrieval_depth, context_cap)` per seed —
   expansion stops as soon as the context cap is reached.
5. Pieces are de-duplicated by name and capped at `context_cap`.

## 17. Multi-Hop Traversal

The Cypher variable-length pattern
`(seed)-[:RELATED_TO*1..depth]-(hop)` returns Neo4j `Path` objects; results are
ordered by route length so the shortest route to each entity is consumed first.
`KnowledgeBase._decompose_path`/`_route_labels` convert each path into a route
string list (`A --[built]-- B --[customer]-- C`), which is attached to the
`ContextPiece` and later shown under each citation. This is how Nexora joins
facts across documents instead of doing literal text matching.

## 18. Answer Generation

1. Evidence entries are numbered (`[1]`, `[2]`, …) by
   `format_context_piece` with entity, kind, summary, source, and graph route.
2. `build_answer_prompt` instructs the model to answer strictly from the
   entries, cite claims inline, avoid inventing facts, and say so when evidence
   is insufficient.
3. The reply is returned as-is; the model decides wording.

## 19. Provenance / Citations

- After generation, `_expand_cited_indices` finds `[n]` and `[1, 3]` groups.
- `_collect_references` maps each index to the matching evidence entry
  (`ProvenanceRecord`), ignoring out-of-range citations.
- The UI shows each verified citation as an expandable source card with
  document, excerpt, and route.
- **Nexora never fabricates citations.** Unverified numbers and
  non-citing answers are rendered without source cards, with an explanatory
  caption.

---

## 20. Error Handling

| Error | Raised when | UI message style |
| --- | --- | --- |
| `UserInputError` | empty/too-short document, missing label, empty question | actionable guidance |
| `StorageError` | Neo4j offline / bad credentials / query failure | “Could not reach…”, “rejected the credentials” |
| `InferenceError` | invalid/missing Gemini key, rate limit, server error, timeout, empty reply | “key was rejected”, “rate limit”, “took too long” |
| `SourceError` | model JSON unusable, extraction empty | “could not analyse…”, “No entities…” |
| `ContextError` | no terms/seeds/context for a question | “Nothing matched…”, “No searchable terms…” |

Unexpected (non-`AppError`) exceptions are logged with a traceback and shown
generically; technical detail never reaches the UI.

---

## 21. Troubleshooting

| Problem | Possible cause | Solution |
| --- | --- | --- |
| Neo4j connection failure | DB not started; wrong URI/port | Start it; verify `NEO4J_URI` |
| Neo4j rejects credentials | Wrong user/password | Fix `NEO4J_USER`/`NEO4J_PASSWORD` in `.env` or sidebar |
| Gemini key missing | `GEMINI_API_KEY` not set | Set it in `.env` or Streamlit secrets |
| Gemini key rejected | Invalid/disabled key | Create a new key in Google AI Studio |
| Gemini rate limited | Free-tier quota exhausted | Wait, or switch `GEMINI_MODEL` |
| Model not available | Wrong model name | Fix `GEMINI_MODEL` |
| Missing environment variables | `.env` missing/renamed | Copy `.env.example` → `.env` and fill in |
| Empty graph | Nothing ingested | Ingest documents first |
| Extraction failure | Model returned junk JSON / too-short text | Try clearer/longer text or a stronger Gemini model |
| Invalid LLM response | Model not obeying JSON instruction | The gateway already requests JSON mode; try another model |
| No retrieval results | Question vocabulary absent from graph | Rephrase with graph terms or ingest more |
| Streamlit errors | Dependency mismatch | `pip install -r requirements.txt`; restart |
| Dependency errors | Missing dev packages | `pip install -r requirements-dev.txt` |
| Model requests hang | Slow network / large prompt | Raise `NEXORA_LLM_TIMEOUT` |

---

## 22. Testing Guide

Run the whole suite:

```bash
python -m pytest
```

Static checks (configured in `pyproject.toml`):

```bash
ruff check .      # lint
ruff format .     # auto-format
```

Warnings are promoted to errors in the test run (`filterwarnings = error`), so
resource leaks and unraisable exceptions fail CI instead of silently passing.

What is tested (all offline; Gemini is mocked, no Neo4j required):

- `test_config.py` — defaults, env parsing, `.env` fallback, env precedence,
  clamping, overrides, signatures.
- `test_models.py` — stable entity ids, truncation, record defaults.
- `test_extraction.py` — JSON recovery, alias fields, deduplication, endpoint
  filtering, error wrapping.
- `test_retrieval.py` — term derivation, seed ranking, context assembly with a
  fake store, early-exit once the context cap is reached.
- `test_answering.py` — citation parsing/verification, answer synthesis.
- `test_llm.py` — prompt formatting, response/model-name extraction, JSON mode,
  and gateway behaviour against an injected fake Gemini client (success, empty
  response, rate limit, server error, auth error, missing key).
- `test_service.py` — input validation that never reaches the network and
  health-report logic exercised against fake connectors/gateways (including
  single-fetch of the available-model list).
- `test_ui_state.py` — the `st.secrets` → environment bridge (Cloud support).

Cannot be tested without live services: real Cypher execution, real Gemini
generation, health probes against a live server. Those are integration tests
you must run manually with services up (System tab → Run diagnostics).

---

## 23. Maintenance Guide

- **Change the LLM/model:** set `GEMINI_MODEL` in `.env` (or sidebar). To change
  *how* the model is prompted, edit `nexora/llm/prompts.py`. To change request
  timeout, `NEXORA_LLM_TIMEOUT`. To change provider entirely, rewrite
  `nexora/llm/gateway.py` (only that module and `config.py`/`errors.py` know
  about Gemini).
- **Change Neo4j configuration:** `.env` (`NEO4J_*`), or sidebar. Schema
  changes go in `nexora/db/statements.py` (+ repository methods).
- **Change extraction behaviour:** `nexora/pipeline/extraction.py` (parsing,
  caps, aliases) and `nexora/llm/prompts.py` (instructions/types).
- **Change retrieval behaviour:** `nexora/pipeline/retrieval.py` (terms,
  stop-words, ranking, seed limit `_MAX_SEEDS_PER_QUERY`) and
  `NEXORA_RETRIEVAL_DEPTH`/`NEXORA_ENTRY_LIMIT`/`NEXORA_CONTEXT_LIMIT`.
- **Change the UI:** everything under `nexora/ui/`. Brand palette/CSS in
  `theme.py`, session plumbing in `state.py`.
- **Change prompts:** only `nexora/llm/prompts.py` (+ tests in `test_llm.py`).
- **Add a new document type/source:** extraction is label-agnostic text; to
  special-case new input formats add ingestion support in `service.py` and a
  matching parser module, then a view entry point.
- **Add new configuration:** add a field to `Settings` in `config.py`, wire it
  into `_ENV_MAP`/`from_environment`/`signature`, add an `.env.example` line,
  and (optionally) a sidebar control.
- **Add tests:** new file under `tests/` (or extend an existing one) and keep
  them free of live-service requirements.

---

## 24. Deployment Considerations

Nexora is designed to run either locally or as a managed web app:

- **Local run** (`streamlit run app.py`) needs only a Neo4j instance and a
  Gemini API key. Streamlit’s dev server, console logs, no auth.
- **Streamlit Community Cloud** is the simplest public deployment. Configuration
  (including `GEMINI_API_KEY`) is provided through the app’s **Secrets**
  dashboard; `nexora/ui/state.py` bridges those secrets into the environment.
  Pair it with a free **Neo4j AuraDB** instance.
- **Docker Compose** (`docker compose up --build`) runs Neo4j + the Streamlit
  app on one host; inference stays on Gemini, so there is no model container.
  Neo4j data lives in the `neo4j_data` named volume.
- **Self-hosted VPS** (Docker Compose + Caddy reverse proxy with Basic Auth) is
  documented in `docs/DEPLOYMENT.md`.
- **Streamlit has no built-in multi-user auth.** For anything beyond a trusted
  LAN, use the reverse proxy in the deployment guide or Streamlit Cloud’s
  privacy settings; there is no user/authorisation model in the app.
- **Secrets** must arrive via environment variables or Streamlit secrets; the
  Compose file uses example Neo4j credentials you should change.
- Streamlit session state resets on restart — no server-side persistence of
  answers/settings (the graph in Neo4j *is* persistent).

## 25. Security Considerations

- **Secret management:** the Gemini API key and Neo4j credentials arrive via
  env/`.env` or Streamlit secrets; `.env` and `.streamlit/secrets.toml` are
  git-ignored; never commit them. `.env.example` holds placeholders only.
- **API key handling:** the Gemini key is never logged, displayed or included
  in `InferenceError` details. The gateway logs only “set”/“missing”.
- **Database credentials:** never logged. `Neo4jConnector` logs only the URI,
  never the password. `Settings.signature()` (which includes secrets) is held
  only in session state, never logged.
- **Data egress:** document text and questions are sent to the Google Gemini
  API for extraction and answering; the knowledge graph stays in Neo4j.
- **Environment variables:** process env takes precedence over `.env`; malformed
  numeric values fall back to safe defaults (clamped).
- **Logging:** log lines never include secrets or document bodies; documents
  are referred to by label. Model replies may appear in error `detail=` strings
  only.
- **Input validation:** Cypher is fully parameterised (no string-built queries
  except the integer depth). Model output is HTML-escaped in the UI before
  rendering to prevent markup injection.
- **Graph scope:** the “erase” wipe deletes **only** Nexora’s own nodes
  (`Entity` and `Document`); unrelated data in a shared database is left
  untouched. Still, prefer a dedicated Nexora database where possible.

## 26. Known Limitations

Honest list of what this version does *not* do:

1. **Keyword retrieval only.** Entry-point matching is substring-based over
   name/kind/summary. There are no embeddings or semantic/vector search, and
   the tokeniser matches Latin alphanumerics (English-oriented; the stop-word
   list is English).
2. **Seed expansion is capped.** Only the top 3 ranked seeds are expanded per
   question.
3. **Entity-level provenance.** Evidence is per *entity*. When one entity is
   mentioned in several documents, the node’s `doc_ref`/`excerpt` reflect the
   most recently ingested document; a citation then resolves to that
   document, and its excerpt is self-consistent with it. The full set of
   documents per entity is preserved in the graph (via `MENTIONED_IN`) but is
   not yet surfaced per citation in the UI.
4. **Excerpt granularity.** Quotes are the first ≤300 characters of a source
   (the whole document text is kept on the `Document` node, but the UI shows
   the truncated excerpt).
5. **Long documents.** The whole document text is sent to the extraction model
   in one call; very long texts may exceed the model’s context window. There
   is no chunking yet.
6. **Citation behaviour depends on the model.** Some models occasionally omit
   inline citations; Nexora cannot force them and will then show an answer
   without source cards.
7. **Text input only.** There is no PDF/DOCX/URL ingestion.
8. **Requires both services.** Full functionality needs a running Neo4j
   database and a valid Gemini API key (and outbound network access to Google).
9. **No schema migration.** Existing graphs are not migrated automatically
   when the schema changes; wipe and re-ingest instead.
10. **Streamlit session state** resets when the server restarts.

## 27. Future Improvements

Ideas that are deliberately *not* claimed as implemented:

- Embeddings / vector search over entity summaries and document text
  (hybrid retrieval).
- Full-text or fuzzy entity matching (e.g. Neo4j full-text indexes).
- Chunking for long documents with per-chunk citations.
- File upload ingestion (PDF, DOCX, markdown).
- Per-citation listing of *every* document that mentions an entity.
- Multi-user authentication and deployment hardening.
- Streaming answer generation in the UI.
- Configurable seed expansion count surfaced in settings.
