# Nexora

**Knowledge Graph Intelligence Engine** — turn documents into a queryable
knowledge graph, then answer questions with grounded, citation-aware reasoning.

Nexora converts plain-text documents into typed **entities** and labelled
**relationships** stored in Neo4j. When you ask a question, it finds the
entities that matter, **walks the graph several hops** to gather connected
evidence from *different* documents, and lets a **local LLM** (Ollama) compose
an answer strictly from that evidence — with every claim traceable to the
source document, excerpt and graph route it relies on.

[![CI](https://github.com/Yug-Gupta/Nexora/actions/workflows/ci.yml/badge.svg)](https://github.com/Yug-Gupta/Nexora/actions)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/ui-Streamlit-FF4B4B)
![Graph DB](https://img.shields.io/badge/graph-Neo4j-4581C3)
![LLM](https://img.shields.io/badge/llm-Ollama-3E4349)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

```
Document → Extraction → Neo4j Graph → Multi-hop Retrieval → Grounded LLM Answer → Verified Citations
```

> Everything runs locally: your documents, your graph and your model never
> leave your machine. No API keys, no data egress.

---

## What makes it different

Typical question-answering tools search for text snippets that literally
contain your keywords. That fails when the answer lives in *two different
documents* — e.g. *"who invested in the company, and what else do they own?"*.

Nexora solves this with a **knowledge-graph approach**:

1. **Extraction** — a local model reads each document and returns a strict
   JSON structure of entities (`PERSON`, `ORGANIZATION`, `PRODUCT`, …) and the
   relationships between them.
2. **Graph storage** — entities are merged into Neo4j by a stable, name-derived
   key, so the *same entity mentioned in many documents collapses into one
   node*. Facts from separate sources become joinable.
3. **Multi-hop retrieval** — a question is decomposed into search terms,
   matching entities become ranked *seeds*, and the graph is walked several
   relationship hops. Indirect links (`A —[rel]— B —[rel]— C`) are discovered
   automatically and every piece of evidence records the route used to reach
   it.
4. **Grounded generation** — the LLM answers from numbered evidence only,
   citing `[1]`, `[2]` inline. Nexora verifies every citation against the real
   evidence and **never fabricates a source card**.

## Key features

- **Real knowledge graph** — typed `Entity` nodes and labelled `RELATED_TO`
  relationships; cross-document entity merging out of the box.
- **GraphRAG retrieval** — keyword-to-seed discovery ranked by relevance, then
  multi-hop expansion reported in shortest-path order.
- **Provenance & citations** — every claim resolves back to its document,
  excerpt and graph route; unverifiable citations are never displayed.
- **Local & private** — extraction and answering run on your own model through
  Ollama; fully offline-capable.
- **Built-in demo** — three linked example documents and suggested questions
  make the pipeline explorable in minutes.
- **Live diagnostics** — one-click health checks for Neo4j, Ollama, the
  configured model and current graph contents.
- **Defensive by design** — malformed model JSON, duplicate entities, unknown
  relation endpoints, offline services and bad credentials are normalised or
  surfaced as clear, user-safe errors.
- **Production hygiene** — fully parameterised Cypher, lazy connections, a
  strict layered architecture, ruff linting and an offline pytest suite.

## Architecture

Nexora is a layered Python application. A **core engine** (`nexora/`) never
imports Streamlit; the **presentation layer** (`nexora/ui/`) never runs Cypher
or builds prompts. They meet at one facade — `nexora.service.KnowledgeAssistant`.

```
┌───────────────────────────── INGESTION ─────────────────────────────┐
│                                                                     │
│   document text ──► local model extracts a JSON graph               │
│                        (entities + relations)                       │
│                             │                                       │
│                             ▼                                       │
│   entities merged into Neo4j by stable name-derived key             │
│   relations created only when both endpoints exist                  │
│   document registered as a provenance node                          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────── RETRIEVAL + GENERATION ─────────────────────┐
│                                                                     │
│   question ──► keywords ──► relevance-ranked seed entities          │
│                                │                                    │
│                                ▼                                    │
│   walk N hops from each seed (shortest routes first)                │
│                                │                                    │
│                                ▼                                    │
│   assemble numbered evidence + graph routes                         │
│                                │                                    │
│                                ▼                                    │
│   local model answers, citing [n] entries inline                    │
│                                │                                    │
│                                ▼                                    │
│   verify citations ──► resolve to sources, excerpts & routes        │
└─────────────────────────────────────────────────────────────────────┘
```

**Separation of concerns** (enforced in code and review):

| Concern | Owned by |
| --- | --- |
| Neo4j driver | `nexora/db/connector.py` (the only module that imports it) |
| Ollama client | `nexora/llm/gateway.py` (the only module that imports it) |
| Cypher queries | `nexora/db/statements.py` |
| Prompt templates | `nexora/llm/prompts.py` |
| Environment access | `nexora/config.py` (no other module reads `os.environ`) |
| Streamlit | `nexora/ui/**` only |

## Try the built-in demo

The repo ships with three example documents that intentionally share entities:

- **Aster Systems — company background**
- **Fernwood Insurance — deployment case**
- **Northgate Capital — portfolio notes**

Together they answer cross-document questions such as *"Which investors back
Aster Systems and what else do they hold?"* — a fact that can only be assembled
by joining evidence across multiple documents through the graph.

## Quick start

### Option A — Docker Compose (fastest)

Neo4j, Ollama **and** the app start together:

```bash
docker compose up --build
```

Once the stack is healthy, install a model inside the Ollama container and open
<http://localhost:8501>:

```bash
docker exec nexora-ollama ollama pull llama3.2
```

### Option B — Run from source

**Prerequisites**

- Python **3.10+**
- A running **Neo4j** instance (Community Edition is enough)
- A running **Ollama** service with a chat model pulled (`ollama pull llama3.2`)

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure the environment (fill in your Neo4j password)
cp .env.example .env            # Windows:  Copy-Item .env.example .env

# 4. Start the app
streamlit run app.py
```

Need a standalone Neo4j in one command?

```bash
docker run -d --name nexora-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

## Configuration

Every setting is optional and has a sensible local-development default. Copy
`.env.example` to `.env` and adjust only what you need. **Real environment
variables always take precedence over `.env`.**

| Variable | Default | Purpose |
| --- | --- | --- |
| `NEO4J_URI` | `bolt://127.0.0.1:7687` | Neo4j Bolt URI |
| `NEO4J_USER` | `neo4j` | Neo4j user name |
| `NEO4J_PASSWORD` | *(empty)* | Neo4j password |
| `NEO4J_DATABASE` | *(empty)* | Database name; server default when blank |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama HTTP endpoint |
| `OLLAMA_MODEL` | `llama3.2` | Model tag for extraction and answering |
| `NEXORA_RETRIEVAL_DEPTH` | `2` | Relationship hops walked per seed (1–6) |
| `NEXORA_CONTEXT_LIMIT` | `18` | Max evidence entries per answer prompt (4–60) |
| `NEXORA_ENTRY_LIMIT` | `8` | Max seed candidates returned by keyword search (1–30) |
| `NEXORA_LLM_TIMEOUT` | `300` | Seconds to wait for one Ollama request (5–3600) |
| `NEXORA_LOG_LEVEL` | `INFO` | Log level for the `nexora` logger tree |

All connection-related values can also be changed at runtime from the app
**sidebar** for the current browser session; the UI never writes to `.env`.

> The bundled `docker-compose.yml` uses example credentials (`neo4j/password`).
> Change them before exposing the stack beyond a trusted machine.

## Using Nexora

1. **Check services** — open the app and run *System status → Run
   diagnostics*. Confirm Neo4j, Ollama and your model are healthy.
2. **Ingest a document** — on the *Ingest knowledge* tab, load a built-in
   example or paste your own text, give it a reference label, and press
   *Analyse and index*. Review the extracted entities and relationships.
3. **Build a connected corpus** — ingest a second example (the samples share
   entities, which demonstrates cross-document joins).
4. **Ask questions** — on the *Ask a question* tab, try a suggested question or
   ask your own. The answer includes an audit of how it was assembled and an
   expandable source card for every verified citation.

## Project layout

```
.
├── app.py                       # Streamlit entry point (run this)
├── nexora/                      # core engine (never imports Streamlit)
│   ├── config.py                # Settings record, .env loading, logging
│   ├── errors.py                # typed errors + exception translators
│   ├── models.py                # domain records & stable entity ids
│   ├── samples.py               # built-in demo documents & questions
│   ├── service.py               # KnowledgeAssistant facade
│   ├── db/
│   │   ├── connector.py         # Neo4j driver lifecycle (sole usage)
│   │   ├── statements.py        # every Cypher statement + schema
│   │   └── repository.py        # KnowledgeBase read/write operations
│   ├── llm/
│   │   ├── gateway.py           # InferenceGateway over the Ollama client
│   │   └── prompts.py           # extraction + answering prompts
│   ├── pipeline/
│   │   ├── extraction.py        # document -> validated entities/relations
│   │   ├── retrieval.py         # question -> seeds -> multi-hop context
│   │   └── answering.py         # evidence -> answer + citation check
│   └── ui/                      # Streamlit views (the only Streamlit layer)
│       ├── __init__.py          # app wiring / tabs
│       ├── theme.py             # brand palette, CSS, HTML helpers
│       ├── state.py             # session-state & error helpers
│       ├── sidebar.py           # connection settings panel
│       ├── ingest_view.py       # document ingestion tab
│       ├── ask_view.py          # question answering tab
│       └── status_view.py       # diagnostics & graph overview tab
├── tests/                       # offline unit tests (no external services)
├── docs/
│   └── NEXORA_PROJECT_GUIDE.md  # complete technical handbook
├── .github/workflows/ci.yml     # lint + test pipeline on push / PR
├── .env.example                 # copy to .env and fill in
├── .dockerignore
├── .gitattributes               # consistent line endings across platforms
├── Dockerfile                   # non-root, headless Streamlit image
├── docker-compose.yml           # Neo4j + Ollama + Nexora together
├── pyproject.toml               # ruff + pytest configuration
├── requirements.txt             # runtime dependencies
├── requirements-dev.txt         # + pytest & ruff
├── CHANGELOG.md
├── SECURITY.md
├── LICENSE
└── .streamlit/config.toml       # visual theme
```

## Development

```bash
pip install -r requirements-dev.txt

python -m pytest                 # run the offline unit suite
ruff check .                     # lint
ruff format .                    # auto-format
```

Quality gates are enforced in CI (`.github/workflows/ci.yml`) on every push and
pull request: **ruff lint**, **ruff format check**, and the **full pytest suite**
across Python 3.10, 3.11 and 3.12. Warnings are promoted to errors during
testing, so resource leaks and unraisable exceptions fail the build instead of
passing silently.

## Documentation

The [project guide](docs/NEXORA_PROJECT_GUIDE.md) is a complete technical
handbook: architecture, data flow, module-by-module reference, Neo4j and Ollama
guides, configuration reference, error taxonomy, maintenance recipes, security
and deployment notes, and a full list of known limitations and future ideas.

## Roadmap

Planned and potential directions (see the guide for the full list):

- Hybrid retrieval with embeddings / vector search.
- Full-text and fuzzy entity matching (Neo4j full-text indexes).
- Chunking for long documents with per-chunk citations.
- File upload ingestion (PDF, DOCX, markdown).
- Per-citation listing of every document that mentions an entity.

## License

Released under the [MIT License](LICENSE). © 2026 Yug Gupta.
