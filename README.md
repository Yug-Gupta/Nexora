# Nexora

**Knowledge Graph Intelligence Engine** — turn documents into a queryable
knowledge graph, then answer questions with grounded, citation-aware reasoning.

Nexora converts plain-text documents into typed **entities** and labelled
**relationships** stored in Neo4j. When you ask a question, it finds the
entities that matter, **walks the graph several hops** to gather connected
evidence from *different* documents, and asks **Google Gemini** to compose an
answer strictly from that evidence — with every claim traceable to the source
document, excerpt and graph route it relies on.

[![CI](https://github.com/Yug-Gupta/Nexora/actions/workflows/ci.yml/badge.svg)](https://github.com/Yug-Gupta/Nexora/actions)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/ui-Streamlit-FF4B4B)
![Graph DB](https://img.shields.io/badge/graph-Neo4j-4581C3)
![LLM](https://img.shields.io/badge/llm-Google%20Gemini-4285F4)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

```
Document → Extraction → Neo4j Graph → Multi-hop Retrieval → Grounded Gemini Answer → Verified Citations
```

> **Data flow:** documents and questions are sent to the **Google Gemini API**
> for extraction and answering. The knowledge graph itself lives in your Neo4j
> database (local Docker or Neo4j AuraDB). Your API key is read only from the
> environment / secrets and is never logged or committed.

---

## What makes it different

Typical question-answering tools search for text snippets that literally
contain your keywords. That fails when the answer lives in *two different
documents* — e.g. *"who invested in the company, and what else do they own?"*.

Nexora solves this with a **knowledge-graph approach**:

1. **Extraction** — Gemini reads each document and returns a strict JSON
   structure of entities (`PERSON`, `ORGANIZATION`, `PRODUCT`, …) and the
   relationships between them.
2. **Graph storage** — entities are merged into Neo4j by a stable, name-derived
   key, so the *same entity mentioned in many documents collapses into one
   node*. Facts from separate sources become joinable.
3. **Multi-hop retrieval** — a question is decomposed into search terms,
   matching entities become ranked *seeds*, and the graph is walked several
   relationship hops. Indirect links (`A —[rel]— B —[rel]— C`) are discovered
   automatically and every piece of evidence records the route used to reach
   it.
4. **Grounded generation** — Gemini answers from numbered evidence only,
   citing `[1]`, `[2]` inline. Nexora verifies every citation against the real
   evidence and **never fabricates a source card**.

## Key features

- **Real knowledge graph** — typed `Entity` nodes and labelled `RELATED_TO`
  relationships; cross-document entity merging out of the box.
- **GraphRAG retrieval** — keyword-to-seed discovery ranked by relevance, then
  multi-hop expansion reported in shortest-path order.
- **Provenance & citations** — every claim resolves back to its document,
  excerpt and graph route; unverifiable citations are never displayed.
- **Managed inference** — extraction and answering run on the Google Gemini API
  (`google-genai`), configurable with a single model name. No self-hosting
  required, which makes it deployable on Streamlit Community Cloud.
- **Built-in demo** — three linked example documents and suggested questions
  make the pipeline explorable in minutes.
- **Live diagnostics** — one-click health checks for Neo4j, the Gemini API, the
  configured model and current graph contents.
- **Defensive by design** — malformed model JSON, duplicate entities, unknown
  relation endpoints, invalid API keys, rate limits and timeouts are normalised
  or surfaced as clear, user-safe errors.
- **Production hygiene** — fully parameterised Cypher, lazy connections, a
  strict layered architecture, ruff linting and an offline pytest suite
  (Gemini is mocked in tests — no live calls).

## Architecture

Nexora is a layered Python application. A **core engine** (`nexora/`) never
imports Streamlit; the **presentation layer** (`nexora/ui/`) never runs Cypher
or builds prompts. They meet at one facade — `nexora.service.KnowledgeAssistant`.

```
┌───────────────────────────── INGESTION ─────────────────────────────┐
│                                                                     │
│   document text ──► Gemini extracts a JSON graph                    │
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
│   Gemini answers, citing [n] entries inline                         │
│                                │                                    │
│                                ▼                                    │
│   verify citations ──► resolve to sources, excerpts & routes        │
└─────────────────────────────────────────────────────────────────────┘
```

**Separation of concerns** (enforced in code and review):

| Concern | Owned by |
| --- | --- |
| Neo4j driver | `nexora/db/connector.py` (the only module that imports it) |
| Gemini client | `nexora/llm/gateway.py` (the only module that imports `google-genai`) |
| Cypher queries | `nexora/db/statements.py` |
| Prompt templates | `nexora/llm/prompts.py` |
| Environment access | `nexora/config.py` (no other engine module reads `os.environ`) |
| Streamlit | `nexora/ui/**` only |

## Get a Gemini API key

1. Open **Google AI Studio** and create an API key (the free tier is enough for
   a demo).
2. Store it as the `GEMINI_API_KEY` environment variable — **never** put it in
   source code, commit it, or paste it into logs/screenshots.
3. Pick a model with `GEMINI_MODEL` (e.g. `gemini-3.6-flash`).

> Older tags such as `gemini-2.5-flash` are no longer served to newly created
> API keys and fail at generation time with `404 NOT_FOUND`. If you see that,
> switch `GEMINI_MODEL` to a current model — the *System status* tab lists
> every model your key can use.

### Never commit your key

`.env` and `.streamlit/secrets.toml` are already **git-ignored**. Keep it that
way. If a key is ever exposed, revoke it in Google AI Studio immediately.

## Quick start

### Option A — Streamlit Community Cloud (recommended for a live link)

This is the easiest way to get a public demo URL, because inference is a managed
API rather than a local model server.

1. Push this repository to GitHub (already done) and sign in at
   <https://share.streamlit.io>.
2. Create a new app pointing at `app.py` on your `main` branch.
3. In **App settings → Secrets**, paste the following (fill in real values):

   ```toml
   GEMINI_API_KEY = "your_gemini_api_key_here"
   GEMINI_MODEL = "gemini-3.6-flash"

   NEO4J_URI = "neo4j+s://<your-instance-id>.databases.neo4j.io"
   NEO4J_USER = "neo4j"
   NEO4J_PASSWORD = "<your-auradb-password>"
   ```

   For Neo4j, the free [Neo4j AuraDB](https://neo4j.com/cloud/aura/) tier is
   sufficient. Locally you would use `bolt://127.0.0.1:7687` instead.
4. Deploy, then open **System status → Run diagnostics** to confirm Neo4j and
   Gemini are healthy.

Settings are read through a small bridge in `nexora/ui/state.py` that copies
recognised `st.secrets` values into the environment; the engine itself never
imports Streamlit.

### Option B — Run locally from source

**Prerequisites**

- Python **3.10+**
- A **Gemini API key**
- A running **Neo4j** instance (local Docker or Neo4j AuraDB)

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure the environment (set GEMINI_API_KEY and Neo4j values)
cp .env.example .env            # Windows:  Copy-Item .env.example .env

# 4. Start a local Neo4j (skip if using AuraDB)
docker run -d --name nexora-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# 5. Start the app
streamlit run app.py
```

### Option C — Docker Compose (Neo4j + app)

A single command starts Neo4j and the Streamlit app (inference stays on Gemini,
so no model container is needed). Put `GEMINI_API_KEY` in your root `.env`
first, then:

```bash
docker compose up --build
```

Open <http://localhost:8501>. To use an external Neo4j instead of the bundled
container, set `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` in `.env`.

> If your `.env` sets `NEO4J_URI=bolt://127.0.0.1:7687` (for local
> `streamlit run`), override it for Compose so the app reaches the container:
> `NEO4J_URI=bolt://graphdb:7687 docker compose up --build`.

## Configuration

Every setting is optional except the API key, and all values have sensible
defaults. Copy `.env.example` to `.env` (local) or use Streamlit secrets
(Cloud). **Real environment variables always take precedence over `.env`.**

| Variable | Default | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | *(empty)* | **Required.** Google Gemini API key (secret) |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Gemini model for extraction and answering |
| `NEO4J_URI` | `bolt://127.0.0.1:7687` | Neo4j Bolt URI (local or `neo4j+s://…` for AuraDB) |
| `NEO4J_USER` | `neo4j` | Neo4j user name |
| `NEO4J_PASSWORD` | *(empty)* | Neo4j password |
| `NEO4J_DATABASE` | *(empty)* | Database name; server default when blank |
| `NEXORA_RETRIEVAL_DEPTH` | `2` | Relationship hops walked per seed (1–6) |
| `NEXORA_CONTEXT_LIMIT` | `18` | Max evidence entries per answer prompt (4–60) |
| `NEXORA_ENTRY_LIMIT` | `8` | Max seed candidates returned by keyword search (1–30) |
| `NEXORA_LLM_TIMEOUT` | `300` | Seconds to wait for one Gemini request (5–3600) |
| `NEXORA_LOG_LEVEL` | `INFO` | Log level for the `nexora` logger tree |

All connection-related values can also be changed at runtime from the app
**sidebar** for the current browser session; the UI never writes to `.env`.

## Using Nexora

1. **Check services** — open the app and run *System status → Run
   diagnostics*. Confirm Neo4j and the Gemini API are healthy and the
   configured model is ready.
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
│   │   ├── gateway.py           # InferenceGateway over google-genai
│   │   └── prompts.py           # extraction + answering prompts
│   ├── pipeline/
│   │   ├── extraction.py        # document -> validated entities/relations
│   │   ├── retrieval.py         # question -> seeds -> multi-hop context
│   │   └── answering.py         # evidence -> answer + citation check
│   └── ui/                      # Streamlit views (the only Streamlit layer)
│       ├── __init__.py          # app wiring / tabs
│       ├── theme.py             # brand palette, CSS, HTML helpers
│       ├── state.py             # session-state, secrets bridge, errors
│       ├── sidebar.py           # connection settings panel
│       ├── ingest_view.py       # document ingestion tab
│       ├── ask_view.py          # question answering tab
│       └── status_view.py       # diagnostics & graph overview tab
├── tests/                       # offline unit tests (Gemini mocked)
├── docs/
│   ├── NEXORA_PROJECT_GUIDE.md  # complete technical handbook
│   └── DEPLOYMENT.md            # self-hosted demo on a VPS
├── deploy/
│   └── Caddyfile                # HTTPS reverse proxy + Basic Auth (VPS)
├── .github/workflows/ci.yml     # lint + test pipeline on push / PR
├── .env.example                 # copy to .env and fill in
├── .dockerignore
├── .gitattributes               # consistent line endings across platforms
├── Dockerfile                   # non-root, headless Streamlit image
├── docker-compose.yml           # Neo4j + the Streamlit app
├── docker-compose.prod.yml      # adds the Caddy proxy (run with the base file)
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

python -m pytest                 # run the offline unit suite (Gemini mocked)
ruff check .                     # lint
ruff format .                    # auto-format
```

Quality gates are enforced in CI (`.github/workflows/ci.yml`) on every push and
pull request: **ruff lint**, **ruff format check**, and the **full pytest suite**
across Python 3.10, 3.11 and 3.12. Warnings are promoted to errors during
testing, so resource leaks and unraisable exceptions fail the build instead of
passing silently. Tests never make live Gemini calls.

## Documentation

- **[Project guide](docs/NEXORA_PROJECT_GUIDE.md)** — complete technical
  handbook: architecture, data flow, module-by-module reference, Neo4j and
  Gemini guides, configuration reference, error taxonomy, maintenance recipes,
  security and deployment notes, and known limitations.
- **[Deployment guide](docs/DEPLOYMENT.md)** — host Nexora as a public,
  always-on demo on a VPS (Docker Compose + Caddy HTTPS proxy with Basic Auth).

## Roadmap

Planned and potential directions (see the guide for the full list):

- A pluggable provider interface so Gemini and other LLMs can be swapped freely.
- Hybrid retrieval with embeddings / vector search.
- Full-text and fuzzy entity matching (Neo4j full-text indexes).
- Chunking for long documents with per-chunk citations.
- File upload ingestion (PDF, DOCX, markdown).

## License

Released under the [MIT License](LICENSE). © 2026 Yug Gupta.
