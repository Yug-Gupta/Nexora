# Nexora

**Knowledge Graph Intelligence Engine — local, private, grounded GraphRAG.**

Nexora turns plain-text documents into a typed **knowledge graph** inside
Neo4j and answers natural-language questions by **walking that graph**
(multi-hop retrieval) while a **local LLM** (via Ollama) reasons strictly over
the retrieved evidence. Every claim is traceable: citations resolve back to
the source document, the excerpt it came from, and the graph route used to
reach it.

[![CI](https://github.com/Yug-Gupta/Nexora/actions/workflows/ci.yml/badge.svg)](https://github.com/Yug-Gupta/Nexora/actions)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

```
Document → Extraction → Neo4j Graph → Multi-hop Retrieval → Grounded LLM Answer → Verified Citations
```

> Everything runs locally: your documents, your graph and your model never
> leave your machine.

---

## Features

- **Real knowledge graph** — documents become typed `Entity` nodes and labelled
  `RELATED_TO` relationships in Neo4j. The same entity mentioned across
  several documents collapses into one shared node, so facts from *separate*
  sources get joined.
- **GraphRAG retrieval** — a question is decomposed into search terms; the
  entities that best match those terms become ranked *seeds*; the graph is
  walked several hops to collect connected evidence. Routes are reported in
  shortest-path order.
- **Grounded, citation-aware answers** — the model answers from numbered
  evidence only, citing `[1]`, `[2]` inline. Nexora verifies each citation
  against the evidence and never fabricates a source card.
- **Full provenance** — every entity remembers the document it came from; every
  retrieved piece records its graph route; every citation resolves to a real
  excerpt.
- **Local & private** — inference runs on your own model through Ollama; no API
  keys, no data egress.
- **Live diagnostics** — one-click health checks for Neo4j, the Ollama service,
  the configured model and the current graph.
- **Defensive by design** — malformed LLM JSON, duplicate entities, unknown
  relation endpoints, offline services and bad credentials are all handled with
  clear, user-safe messages.
- **No secrets in code** — all credentials arrive via environment variables or
  a local `.env` file; nothing is hard-coded.
- **Production tooling** — parameterised Cypher only, lazy connections,
  layered architecture, ruff linting, and a pytest suite that needs **no** live
  services.

## Architecture

Nexora is a layered Python package. A core engine (`nexora/`) never imports
Streamlit; the UI (`nexora/ui/`) never runs Cypher or builds prompts. They meet
at one facade: `nexora.service.KnowledgeAssistant`.

```
┌──────────────────────────── INGESTION ─────────────────────────────┐
│                                                                    │
│   document text ──► local model extracts a JSON graph              │
│                        (entities + relations)                      │
│                             │                                      │
│                             ▼                                      │
│   entities merged into Neo4j by stable name-derived key            │
│   relations created only when both endpoints exist                 │
│   document registered as a provenance node                         │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────── RETRIEVAL + GENERATION ─────────────────────┐
│                                                                    │
│   question ──► keywords ──► relevance-ranked seed entities         │
│                                │                                   │
│                                ▼                                   │
│   walk N hops from each seed (shortest routes first)               │
│                                │                                   │
│                                ▼                                   │
│   assemble numbered evidence + graph routes                        │
│                                │                                   │
│                                ▼                                   │
│   local model answers, citing [n] entries inline                   │
│                                │                                   │
│                                ▼                                   │
│   verify citations ──► resolve to sources, excerpts & routes       │
└────────────────────────────────────────────────────────────────────┘
```

The separation of concerns is strict and enforced by review:

- Only `nexora/db/connector.py` touches the Neo4j driver.
- Only `nexora/llm/gateway.py` touches the Ollama client.
- Only `nexora/ui/**` imports Streamlit.
- Every Cypher query lives in `nexora/db/statements.py`.
- Every prompt lives in `nexora/llm/prompts.py`.
- No module reads `os.environ` except `nexora/config.py`.

## Quick start

### Option A — Docker Compose (recommended for trying it out)

Neo4j, Ollama **and** the Nexora app start together:

```bash
docker compose up --build
```

Once the stack is healthy, install a model inside the Ollama container:

```bash
docker exec nexora-ollama ollama pull llama3.2
```

Open <http://localhost:8501>.

### Option B — Run from source

**Prerequisites**

- Python **3.10+**
- A running **Neo4j** instance (Community Edition is enough)
- A running **Ollama** service with a chat model pulled (`ollama pull llama3.2`)

**Steps**

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

Open the URL printed by Streamlit (normally <http://localhost:8501>).

> Need a local Neo4j in one command?
> `docker run -d --name nexora-neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest`

## Configuration

All settings are optional — every value has a sensible local-development
default. Copy `.env.example` to `.env` and adjust only what you need. Real
environment variables always take precedence over `.env`.

| Variable                | Default                      | Purpose                                        |
| ----------------------- | ---------------------------- | ---------------------------------------------- |
| `NEO4J_URI`             | `bolt://127.0.0.1:7687`      | Neo4j Bolt URI                                 |
| `NEO4J_USER`            | `neo4j`                      | Neo4j user name                                |
| `NEO4J_PASSWORD`        | *(empty)*                    | Neo4j password                                 |
| `NEO4J_DATABASE`        | *(empty)*                    | Database name; server default when blank       |
| `OLLAMA_BASE_URL`       | `http://127.0.0.1:11434`     | Ollama HTTP endpoint                           |
| `OLLAMA_MODEL`          | `llama3.2`                   | Model tag used for extraction and answering    |
| `NEXORA_RETRIEVAL_DEPTH`| `2`                          | Relationship hops walked per seed (1–6)        |
| `NEXORA_CONTEXT_LIMIT`  | `18`                         | Max evidence entries per answer prompt (4–60)  |
| `NEXORA_ENTRY_LIMIT`    | `8`                          | Max seed candidates returned by keyword search  |
| `NEXORA_LLM_TIMEOUT`    | `300`                        | Seconds to wait for one Ollama request (5–3600)|
| `NEXORA_LOG_LEVEL`      | `INFO`                       | Log level for the `nexora` logger tree         |

All connection-related values can also be overridden at runtime from the
**sidebar** of the running app (per browser session). Nothing is ever written
back to `.env` by the UI.

## Usage

1. Open the app and run **System status → Run diagnostics** to confirm Neo4j,
   Ollama and your model are healthy.
2. On the **Ingest knowledge** tab, load a built-in example or paste your own
   text, give the document a label, and press **Analyse and index**.
3. Ingest a second example — the sample documents share entities, which
   demonstrates how Nexora joins facts across sources.
4. On the **Ask a question** tab, try a suggested question or ask your own. The
   answer renders with an audit trail and expandable source evidence for every
   citation.

## Project layout

```
.
├── app.py                       # Streamlit entry point (run this)
├── nexora/
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
├── Dockerfile
├── docker-compose.yml           # Neo4j + Ollama + Nexora together
├── pyproject.toml               # ruff + pytest configuration
├── requirements.txt
├── requirements-dev.txt
├── LICENSE
└── .streamlit/config.toml       # visual theme
```

## Development

```bash
pip install -r requirements-dev.txt

python -m pytest                 # run the offline unit suite
ruff check .                     # lint
ruff format .                    # format
```

The full technical handbook — architecture, per-module reference, data flow,
Neo4j and Ollama guides, maintenance recipes and known limitations — lives in
[`docs/NEXORA_PROJECT_GUIDE.md`](docs/NEXORA_PROJECT_GUIDE.md).

## Testing

The pytest suite covers configuration loading, entity identifiers, extraction
parsing, retrieval term/ranking/context logic, prompt assembly, citation
verification and gateway response handling — all **offline**, with **no** live
Neo4j or Ollama required:

```bash
python -m pytest
```

CI runs linting (ruff) and the full test suite across Python 3.10, 3.11 and
3.12 on every push and pull request.

## Roadmap

See the *Known limitations* and *Future improvements* sections of the
[project guide](docs/NEXORA_PROJECT_GUIDE.md) for an honest list of what this
version does and does not do (e.g. no embeddings yet, text input only, no
multi-user auth).

## License

[MIT](LICENSE) © 2026 Yug Gupta.
