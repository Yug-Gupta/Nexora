# Nexora

**Knowledge Graph Intelligence Engine** — turn documents into a queryable
knowledge graph, then answer questions with grounded, citation-aware reasoning.

[![CI](https://github.com/Yug-Gupta/Nexora/actions/workflows/ci.yml/badge.svg)](https://github.com/Yug-Gupta/Nexora/actions)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/ui-Streamlit-FF4B4B)
![Graph DB](https://img.shields.io/badge/graph-Neo4j-4581C3)
![LLM](https://img.shields.io/badge/llm-Google%20Gemini-4285F4)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

## Live Demo

**https://nexoraengine.streamlit.app/**

The application is deployed and running. Open the link, go to **System status →
Run diagnostics** to confirm the services are healthy, then ingest a document
and ask a question.

> If the link asks you to sign in, the deployment's sharing/privacy setting is
> not public — see [Deployment](#deployment).

---

## Overview

NexoraEngine converts plain-text documents into typed **entities** and labelled
**relationships** stored in Neo4j. When you ask a question it finds the entities
that matter, **walks the graph several hops** to gather connected evidence from
*different* documents, and asks **Google Gemini** to compose an answer strictly
from that evidence — with every claim traceable to the source document, excerpt
and graph route it relies on.

### The problem it solves

Ordinary keyword search and naive RAG return text snippets that literally
contain your keywords. That fails when the answer is spread across sources —
for example, *"who invested in the company, and what else do they own?"*, where
the investor, the company and the second holding live in three different
documents. A graph makes those indirect links explicit and traversable.

### Why it exists

NexoraEngine is a compact, production-shaped reference implementation of
**GraphRAG**: it demonstrates document ingestion, LLM-based information
extraction, a real graph store, multi-hop retrieval, grounded generation and
citation verification — with a strict layered architecture, typed error
handling, an offline test suite and deployable packaging.

### Who can use it

- **Developers / data engineers** learning or evaluating GraphRAG patterns.
- **Analysts and researchers** who want to query a small private corpus and
  see exactly which source supports each statement.
- **Teams** wanting a self-hostable, provider-managed (no local GPU) knowledge
  assistant they can extend.

## Features

- **Real knowledge graph** — typed `Entity` nodes and labelled `RELATED_TO`
  relationships, with deterministic cross-document entity merging.
- **GraphRAG retrieval** — keyword-to-seed discovery ranked by relevance, then
  multi-hop expansion reported in shortest-path order.
- **Grounding and citations** — answers must cite numbered evidence; every
  citation is verified against the real evidence before it is displayed, and
  unverifiable ones are never shown.
- **Provenance** — each cited claim resolves to its document, excerpt and graph
  route; documents are stored as first-class `Document` nodes.
- **Managed inference** — extraction and answering run on the Google Gemini API
  (`google-genai`), configurable with a single model name. No local model
  server, so it deploys to a small host or a free managed platform.
- **Resilience** — transient Gemini 5xx errors are retried with exponential
  backoff; malformed model JSON, duplicate entities, unknown relation endpoints,
  invalid keys, rate limits and timeouts are normalised or surfaced as clear,
  user-safe errors.
- **Built-in demo** — three linked sample documents and suggested questions make
  the whole pipeline explorable in minutes.
- **Live diagnostics** — one-click health checks for Neo4j, the Gemini API, the
  configured model and current graph contents.
- **Session-scoped overrides** — Neo4j/Gemini/retrieval settings can be changed
  live from the sidebar without touching `.env`.
- **Production hygiene** — fully parameterised Cypher, lazy connections, a
  strict layered architecture, ruff linting and an offline pytest suite (Gemini
  is mocked; no live calls in tests).

## How It Works

```
Document → Extraction → Neo4j Graph → Multi-hop Retrieval → Grounded Answer → Verified Citations
```

1. **Extraction** — Gemini reads each document and returns strict JSON:
   entities (`PERSON`, `ORGANIZATION`, `PRODUCT`, `TECHNOLOGY`, `LOCATION`,
   `EVENT`, `CONCEPT`) and the relationships between them. The response is
   normalised and validated (JSON-fence recovery, field aliases, de-duplication,
   dangling-endpoint filtering, size caps).
2. **Graph storage** — entities are merged into Neo4j by a stable,
   name-derived key, so the *same entity mentioned in many documents collapses
   into one node*. Each source is recorded as a `Document` node and linked to
   the entities it mentions (`MENTIONED_IN`). Relationships are created only
   when both endpoints exist.
3. **Multi-hop retrieval** — a question is decomposed into search terms, matching
   entities are ranked as *seeds*, and the graph is walked several relationship
   hops. Indirect links (`A —[rel]— B —[rel]— C`) are discovered automatically,
   and every piece of evidence records the route used to reach it.
4. **Grounded generation** — Gemini answers from the numbered evidence only,
   citing `[1]`, `[2]` inline. Nexora verifies every citation against the real
   evidence and never fabricates a source card.

> **Data flow:** document text and questions are sent to the **Google Gemini
> API** for extraction and answering. The knowledge graph lives in your Neo4j
> database (local Docker or Neo4j AuraDB). API keys are read only from the
> environment / secrets and are never logged or committed.

## Architecture

NexoraEngine is a layered Python application. A **core engine** (`nexora/`)
never imports Streamlit; the **presentation layer** (`nexora/ui/`) never runs
Cypher or builds prompts. They meet at one facade — `nexora.service.KnowledgeAssistant`.

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

## Tech Stack

| Technology | What it is | Where it is used | Why it was selected |
| --- | --- | --- | --- |
| **Python 3.10+** | General-purpose language | Entire project | Modern typing (`X \| None`, `zip(strict=…)`), broad ecosystem, easy deployment. |
| **Streamlit** (`>=1.48.0`) | Data-app framework | `app.py`, `nexora/ui/**` | Turns Python into an interactive web UI with no separate frontend, which keeps the project single-language and quick to demo. |
| **Neo4j** + official **`neo4j`** driver (`>=5.0.0`) | Graph database | `nexora/db/**` | Native labelled property graph with variable-length path queries — exactly what multi-hop traversal and provenance need. |
| **Google Gemini** via **`google-genai`** (`>=1.0.0`) | Managed LLM API | `nexora/llm/gateway.py` | High-quality JSON-constrained extraction and generation without hosting a model; deployable anywhere with internet access. |
| **Docker / Docker Compose** | Containerisation | `Dockerfile`, `docker-compose*.yml` | One command to run Neo4j + the app; consistent local and server environments. |
| **Caddy** | Web server / reverse proxy | `deploy/Caddyfile` (prod overlay) | Automatic HTTPS and one-line Basic Auth in front of Streamlit. |
| **pytest** | Test framework | `tests/**` | Offline unit tests with fixtures and warnings-as-errors. |
| **ruff** | Linter + formatter | `pyproject.toml`, CI | Fast, single tool for lint and format; configured in `pyproject.toml`. |

No local inference runtime, embedding model or vector database is used.

## Project Structure

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
├── deploy/
│   └── Caddyfile                # HTTPS reverse proxy + Basic Auth (VPS)
├── .github/workflows/ci.yml     # lint + test pipeline on push / PR
├── .env.example                 # copy to .env and fill in
├── .dockerignore
├── .gitattributes               # consistent line endings across platforms
├── .streamlit/config.toml       # visual theme
├── Dockerfile                   # non-root, headless Streamlit image
├── docker-compose.yml           # Neo4j + the Streamlit app
├── docker-compose.prod.yml      # adds the Caddy proxy (run with the base file)
├── pyproject.toml               # ruff + pytest configuration
├── requirements.txt             # runtime dependencies
├── requirements-dev.txt         # + pytest & ruff
├── CHANGELOG.md
├── SECURITY.md
└── LICENSE
```

## Installation & Setup

### Prerequisites

- **Python 3.10+**
- A **Google Gemini API key** (the free tier is enough for a demo) —
  create one in Google AI Studio.
- A running **Neo4j** instance: local Docker (`neo4j:latest`) or a free
  **Neo4j AuraDB** instance.

### 1. Get the code and create a virtual environment

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt        # runtime
pip install -r requirements-dev.txt    # + pytest and ruff (development)
```

### 3. Configure the environment

```bash
cp .env.example .env                    # Windows: Copy-Item .env.example .env
```

Edit `.env` and set at least:

```dotenv
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.6-flash
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

Every setting is optional except `GEMINI_API_KEY`; all values have sensible
defaults. Real environment variables always take precedence over `.env`.

### 4. Start Neo4j (skip if using AuraDB)

```bash
docker run -d --name nexora-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

Neo4j Browser: <http://localhost:7474> · Bolt: `bolt://127.0.0.1:7687`.

### 5. Start the app

```bash
streamlit run app.py
```

Open <http://localhost:8501>.

### Configuration reference

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

Connection-related values can also be changed at runtime from the app
**sidebar** for the current browser session; the UI never writes to `.env`.

> Older Gemini tags such as `gemini-2.5-flash` may still be listed by the API
> but are no longer served to newly created keys and fail at generation time
> with `404 NOT_FOUND`. If that happens, switch `GEMINI_MODEL` to a current
> model — the *System status* tab lists every model your key can use.

## Usage

NexoraEngine has three tabs.

1. **Check services** — open the app and run **System status → Run
   diagnostics**. Confirm Neo4j and the Gemini API are healthy and the
   configured model is ready.
2. **Ingest a document** — on **Ingest knowledge**, load a built-in example or
   paste your own text, give it a reference label, and press **Analyse and
   index**. Review the extracted entities and relationships.
3. **Build a connected corpus** — ingest a second example. The samples share
   entities, which demonstrates cross-document joins.
4. **Ask a question** — on **Ask a question**, try a suggested question or ask
   your own. The answer includes an audit of how it was assembled and an
   expandable source card for every verified citation.

## Deployment

**Live application: https://nexoraengine.streamlit.app/**

Because inference is a managed API rather than a local model server, the project
deploys to a free managed platform or a small VPS. Three supported shapes:

### Streamlit Community Cloud (recommended for a public link)

1. Connect this repository (`main` branch, main file `app.py`) to
   [share.streamlit.io](https://share.streamlit.io) and create the app.
2. In **App settings → Secrets**, paste (fill in real values):

   ```toml
   GEMINI_API_KEY = "your_gemini_api_key_here"
   GEMINI_MODEL = "gemini-3.6-flash"

   NEO4J_URI = "neo4j+s://<your-instance-id>.databases.neo4j.io"
   NEO4J_USER = "neo4j"
   NEO4J_PASSWORD = "<your-auradb-password>"
   ```

3. Deploy, open the URL, and run **System status → Run diagnostics**.

The engine never imports Streamlit: `nexora/ui/state.py` copies recognised
`st.secrets` values into the environment before settings are read, so no code
changes are required. The cloud host cannot reach a laptop's `localhost`, so
point `NEO4J_URI` at a Neo4j AuraDB instance.

### Docker Compose (Neo4j + app on one host)

Put `GEMINI_API_KEY` in your root `.env`, then:

```bash
docker compose up --build
```

Open <http://localhost:8501>. To reach an external Neo4j instead of the bundled
container, set `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` in `.env`.

> If `.env` sets `NEO4J_URI=bolt://127.0.0.1:7687` (for local `streamlit run`),
> override it for Compose so the app reaches the container:
> `NEO4J_URI=bolt://graphdb:7687 docker compose up --build`.

### Self-hosted VPS with HTTPS + Basic Auth

The production overlay adds a Caddy reverse proxy (automatic HTTPS, Basic Auth):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Set `APP_DOMAIN`, `AUTH_USER` and `AUTH_HASH` in `.env` (generate the hash with
`docker run --rm caddy:2 caddy hash-password --plaintext 'your-password'`) and
firewall the host so only ports `22/80/443` are reachable.

## Security

- **Secrets are never in code.** The Gemini API key and Neo4j password arrive
  via environment variables, a git-ignored `.env`, or Streamlit secrets.
  `.env.example` holds placeholders only; `.env` and
  `.streamlit/secrets.toml` are git-ignored.
- **Keys are never logged or displayed.** The gateway logs only whether a key is
  present, and `InferenceError` messages never include the key. Database
  credentials are never logged either.
- **Fully parameterised Cypher.** The only interpolated query value is a
  validated integer hop depth. User input cannot alter query structure.
- **HTML output is escaped.** Model and user text is HTML-escaped before it is
  rendered, preventing markup injection.
- **Scoped reset.** The "erase the graph" action deletes only Nexora's own
  `Entity` and `Document` nodes, leaving unrelated data in a shared database
  intact.
- **Awareness of data egress.** Document text and questions are sent to the
  Google Gemini API; the graph itself stays in your Neo4j database.
- **No built-in multi-user authentication.** Streamlit has no user model. For a
  public deployment, use the Caddy Basic Auth proxy, your managed host's app
  privacy controls, or an identity-aware proxy.
- **Reporting.** See [SECURITY.md](SECURITY.md) for the security policy.

## Performance

- **Offline test suite runs in seconds** — all Gemini calls are mocked, so CI
  and local tests need no API key, network or database.
- **Single model round-trip per operation** — one `generate_content` call for
  extraction and one for answering; the health check fetches the model list
  exactly once and reuses it for both probes.
- **Shortest-route-first traversal** — the multi-hop query orders paths by
  length, so the closest evidence is consumed first and the context cap ends
  expansion early.
- **Expansion stops at the cap** — once `NEXORA_CONTEXT_LIMIT` entries are
  gathered, no further seeds are expanded (verified by a test).
- **Lazy connections** — the Neo4j driver opens a socket only on first use, so
  the app starts instantly even when the database is offline.
- **Cached resources per session** — the `KnowledgeAssistant` and settings are
  cached in Streamlit session state and only rebuilt when settings change.
- **Configurable depth/limits** — `NEXORA_RETRIEVAL_DEPTH`,
  `NEXORA_ENTRY_LIMIT` and `NEXORA_CONTEXT_LIMIT` bound the work per question.

## Limitations

Honest list of what this version does **not** do:

- **Keyword retrieval only.** Entry-point matching is substring-based over
  name/kind/summary. There are no embeddings or vector search, and the tokeniser
  and stop-word list are English-oriented.
- **Seed expansion is capped** at the top 3 ranked seeds per question.
- **Entity-level provenance.** Evidence is per entity; if an entity appears in
  several documents, the node's `doc_ref`/excerpt reflect the most recent
  ingestion. The full set of mentioning documents is stored (`MENTIONED_IN`) but
  not yet surfaced per citation in the UI.
- **Excerpt granularity.** Citations show the first ≤300 characters of a source.
- **No chunking.** The whole document is sent to the extraction model in one
  call; very long documents may exceed the model's context window.
- **Citations depend on the model.** Some models occasionally omit inline
  citations; Nexora cannot force them and will show the answer without source
  cards.
- **Text input only.** No PDF/DOCX/URL ingestion yet.
- **Requires both services.** Full functionality needs a running Neo4j instance
  and a valid Gemini API key (with outbound network access).
- **No schema migration.** Existing graphs are not migrated automatically when
  the schema changes; wipe and re-ingest instead.
- **Session state is not persisted.** Streamlit state resets on restart (the
  graph in Neo4j is the durable store).

## Future Improvements

- Embeddings / vector search for hybrid retrieval.
- Full-text or fuzzy entity matching (Neo4j full-text indexes).
- Chunking for long documents with per-chunk citations.
- File upload ingestion (PDF, DOCX, markdown).
- Per-citation listing of every document that mentions an entity.
- Streaming answer generation in the UI.
- A pluggable LLM provider interface.
- Configurable seed-expansion count surfaced in settings.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| "The Gemini API key is not configured" | `GEMINI_API_KEY` not set | Set it in `.env` (local) or the deployment's Secrets, then restart. |
| "The Gemini API key was rejected" | Invalid/disabled key | Create a new key in Google AI Studio. |
| "rate limit was reached" | Free-tier quota hit | Wait, or switch `GEMINI_MODEL` to a lighter model. |
| "took too long to answer" | Slow network / large prompt | Raise `NEXORA_LLM_TIMEOUT` or use a faster model. |
| "Could not reach the Neo4j server" | Neo4j not running / wrong URI | Start Neo4j; on Compose use `bolt://graphdb:7687`. |
| "Neo4j rejected the credentials" | Wrong user/password | Fix `NEO4J_USER`/`NEO4J_PASSWORD`. |
| "model … not available" | Wrong or retired model name | Set `GEMINI_MODEL` to a model listed by diagnostics. |
| "Nothing in the knowledge graph matched" | Empty graph / unfamiliar wording | Ingest related documents or rephrase with graph terms. |
| "No entities could be extracted" | Text too short/unclear | Paste longer, clearly written text. |
| Blank page behind the proxy | Streamlit not healthy on 8501 | Check `docker compose logs studio`. |
| Dependency error on start | Environment out of date | `pip install -r requirements.txt` and restart. |

## Development

```bash
pip install -r requirements-dev.txt

python -m pytest                 # offline unit suite (Gemini mocked), 77 tests
ruff check .                     # lint
ruff format .                    # auto-format
```

Quality gates are enforced in CI on every push and pull request: **ruff lint**,
**ruff format check**, and the **full pytest suite** across Python 3.10, 3.11
and 3.12. Warnings are promoted to errors during testing, and tests never make
live Gemini calls.

## License

Released under the [MIT License](LICENSE). © 2026 Yug Gupta.
