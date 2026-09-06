# Verigraph

Verigraph is a graph-grounded question-answering workspace. It reads plain
text documents, turns their contents into a typed *entity graph*, and answers
natural-language questions by walking that graph and having a **local** LLM
reason over the retrieved evidence — with each claim traceable back to the
source excerpt it relies on.

It is a self-contained implementation of a **GraphRAG** workflow: retrieval
that goes beyond single-document lookups by following relationships across
documents (multi-hop reasoning), and answers whose provenance is verifiable
in the interface.

- Graph storage: Neo4j
- Local inference: Ollama (any chat model, e.g. `llama3.2`)
- Interface: Streamlit
- Language: Python 3.9+

---

## Feature overview

- **Structured extraction** — a local model converts pasted text into typed
  entities and labelled relationships described by a short rationale.
- **Cross-document entity graph** — the same entity mentioned in two documents
  collapses into one node, so facts from separate sources can be joined.
- **Keyword seed discovery** — a question is decomposed into search terms used
  to find candidate starting entities.
- **Multi-hop expansion** — from each starting point the graph is walked
  several relationship hops; each hop records the route that was followed.
- **Grounded answering** — retrieved evidence is presented to the model as
  numbered entries with instructions to cite them as `[1]`, `[2]`, and so on.
- **Verifiable citations** — every bracket citation in the generated answer is
  resolved back to its source document, excerpt and graph route, and shown in
  the UI.
- **Diagnostics panel** — live checks of Neo4j, the Ollama service, the
  configured model and the current graph contents.
- **No secrets in code** — all credentials arrive through environment
  variables or a local `.env` file.

## How it works

```
                    ingestion                        retrieval + generation
┌──────────────────────────────┐     ┌─────────────────────────────────────────────┐
│  document text               │     │  question                                   │
│        │                     │     │      │                                     │
│  model extracts JSON graph   │     │  keyword terms -> seed entities             │
│  (entities + relations)      │     │      │                                     │
│        │                     │     │  walk N hops from each seed                 │
│  entities merged into Neo4j  │     │      │                                     │
│  relations linked to them    │     │  assemble numbered evidence + routes        │
└──────────────────────────────┘     │      │                                     │
                                     │  model answers, citing [n] entries          │
                                     │      │                                     │
                                     │  verify citations -> sources & quotes       │
                                     └─────────────────────────────────────────────┘
```

### Ingestion workflow

1. Paste a document (or load a built-in example) and give it a reference
   label.
2. Verigraph asks the local model to return a strict JSON structure:
   `entities` (name, type, one-sentence summary) and `relations`
   (source, target, predicate, context).
3. Each entity is merged into the graph using a stable identifier derived
   from its name, so repeated mentions across documents enrich the same node.
4. Each relation is created only if **both** endpoints already exist; orphaned
   relations are skipped and reported.
5. The extractor results are shown as tables so you can review what was stored.

### Retrieval and answering workflow

1. The question is tokenised into concrete keywords (stop-words removed).
2. Nodes whose name, type or summary contain any keyword become *seeds*.
3. From the top seeds the graph is walked up to `VERIGRAPH_DEPTH` hops; every
   reached entity becomes a context entry together with the route
   `A --[predicate]-- B --[predicate]-- C` that led to it.
4. Entries are numbered and handed to the model with the instruction to ground
   every claim in one or more of them and to cite them inline.
5. Bracket citations found in the model output are matched back against the
   evidence set. Only citations that resolve to a real entry are shown as
   sources; the answer also carries a reasoning log describing the search.

## Project layout

```
.
├── app.py                     # Streamlit entry point (UI only)
├── requirements.txt
├── .env.example               # copy to .env and fill in
├── .streamlit/config.toml     # visual theme
├── Dockerfile
├── docker-compose.yml         # graphdb + modelbox + studio
├── verigraph/
│   ├── __init__.py
│   ├── config.py              # central Settings record + .env loading + logging
│   ├── errors.py              # error taxonomy + exception translators
│   ├── models.py              # domain records (Entity, Relation, Provenance, ...)
│   ├── samples.py             # built-in demo documents
│   ├── service.py             # KnowledgeAssistant facade for the UI
│   ├── db/
│   │   ├── connector.py       # Neo4j driver lifecycle (the only place driver is used)
│   │   ├── statements.py      # every Cypher statement + the graph schema
│   │   └── repository.py      # KnowledgeBase: graph read/write operations
│   ├── llm/
│   │   ├── gateway.py         # InferenceGateway wrapping the Ollama client
│   │   └── prompts.py         # extraction + answering prompt templates
│   └── pipeline/
│       ├── extraction.py      # document -> validated entities & relations
│       ├── retrieval.py       # keywords -> seeds -> multi-hop context
│       └── answering.py       # evidence -> grounded answer + citation check
```

## Requirements

- Python 3.9 or newer
- A running Neo4j instance (community edition is enough)
- A running Ollama service with at least one chat model pulled
  (e.g. `ollama pull llama3.2`)

Python dependencies are intentionally few:

- `streamlit` — the interface
- `neo4j` — the official database driver
- `ollama` — the official Ollama client

## Installation

```bash
pip install -r requirements.txt
```

## Environment configuration

All configuration lives in environment variables. Copy the template and edit
it:

```bash
cp .env.example .env
```

The application reads `.env` from the repository root automatically, so on
most systems you never need to export anything yourself. Every variable is
optional and has a sensible default (local Neo4j on `bolt://127.0.0.1:7687`,
Ollama on `http://127.0.0.1:11434`, model `llama3.2`).

You can also override any of these values at runtime from the **sidebar**
of the running app; those overrides apply to the current browser session only.

### Neo4j setup

The fastest path to a local database is Docker:

```bash
docker run -d --name verigraph-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

Then point the app at it with `NEO4J_URI=bolt://127.0.0.1:7687`,
`NEO4J_USER=neo4j` and `NEO4J_PASSWORD=password`.

A single command runs Neo4j **and** Ollama **and** the app together — see
[Running everything with Docker Compose](#running-everything-with-docker-compose).

### Ollama setup

Install Ollama for your platform, then pull the model you want to use:

```bash
ollama pull llama3.2
```

Set `OLLAMA_BASE_URL` if Ollama is not on `http://127.0.0.1:11434`, and
`OLLAMA_MODEL` to the tag you pulled. The model is resolved at runtime, so
you can switch freely without changing code.

## Running the application

```bash
streamlit run app.py
```

Then open the printed URL (normally `http://localhost:8501`).

1. Open **Add sources**, pick an example or paste text, give it a label and
   press *Analyse and index*.
2. Repeat with a second example — the sample documents are designed to share
   entities, which demonstrates cross-document joins.
3. Open **Ask questions** and try a suggested question, or ask your own.
4. Open **System status** to run diagnostics and inspect (or erase) the graph.

### Running everything with Docker Compose

The bundled compose file starts Neo4j, Ollama and the Streamlit app and wires
them together with the right addresses:

```bash
docker compose up --build
```

Ollama inside the container starts empty; pull a model once it is healthy:

```bash
docker exec verigraph-ollama ollama pull llama3.2
```

## Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| "Could not reach the Neo4j server" | The database is not running or the URI/port is wrong. Start it and verify `NEO4J_URI`. |
| "Neo4j rejected the credentials" | Wrong `NEO4J_USER` / `NEO4J_PASSWORD` for the database. |
| "Could not reach the Ollama service" | Ollama is not running or `OLLAMA_BASE_URL` is incorrect. |
| "The requested model is not installed" | Run `ollama list`; pull the configured model with `ollama pull <tag>`. |
| "No entities could be extracted" | The model returned unusable JSON, or the text is too short/vague. Try clearer text and confirm the model works in `ollama run <tag>`. |
| Nothing matches my question | The question uses words not present in the graph. Ingest related documents or rephrase with graph vocabulary. |
| Answers rarely cite sources | Smaller models skip inline citations. Re-ask, or raise `VERIGRAPH_CONTEXT_LIMIT`, or use a larger model. |

Runtime errors are logged to the console with a timestamp and module name.
Keep secrets out of the logs by never printing the database password.

## Configuration reference

| Variable | Default | Purpose |
| --- | --- | --- |
| `NEO4J_URI` | `bolt://127.0.0.1:7687` | Neo4j connection URI |
| `NEO4J_USER` | `neo4j` | Neo4j user name |
| `NEO4J_PASSWORD` | *(empty)* | Neo4j password |
| `NEO4J_DATABASE` | *(empty)* | Database name; server default when blank |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama HTTP endpoint |
| `OLLAMA_MODEL` | `llama3.2` | Model tag used for extraction and answering |
| `VERIGRAPH_DEPTH` | `2` | Relationship hops walked from each seed (1–6) |
| `VERIGRAPH_ENTRY_LIMIT` | `8` | Max seed candidates returned by keyword search |
| `VERIGRAPH_CONTEXT_LIMIT` | `18` | Max evidence entries included in an answer prompt |
| `VERIGRAPH_LOG_LEVEL` | `INFO` | Log level for the `verigraph` logger tree |

## Architecture notes

- **Separation of concerns.** `app.py` handles only presentation. Domain
  operations live behind `KnowledgeAssistant`; prompts are isolated in
  `llm/prompts.py`; every Cypher statement lives in `db/statements.py`;
  configuration is centralised in `config.py`. No module reaches into the
  driver, the Ollama client or `os.environ` on its own.
- **Single abstraction point for each service.** `db/connector.py` is the only
  place `GraphDatabase.driver` appears and `llm/gateway.py` the only place the
  Ollama client is used, which keeps connection handling and error translation
  in one spot.
- **Stable entity identity.** Node keys are derived from the normalised entity
  name, so the same entity is merged across documents rather than duplicated.
- **Failures are legible.** Errors are typed (`StorageError`, `InferenceError`,
  `SourceError`, `ContextError`, `UserInputError`), carry a message intended
  for end users, and keep technical detail separate for the logs.
