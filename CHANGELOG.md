# Changelog

All notable changes to Nexora are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Migrated inference from Ollama to the Google Gemini API** using the
  official `google-genai` SDK. The application-facing gateway interface
  (`complete`, `available_models`, `model_is_installed`) is unchanged, so the
  UI and pipeline remain provider-agnostic.
- Configuration now uses `GEMINI_API_KEY` (secret) and `GEMINI_MODEL`; the
  Ollama endpoint/model variables are gone. Neo4j settings are unchanged and
  remain fully configurable for AuraDB.
- Extraction uses Gemini JSON response mode; malformed output, missing keys,
  API errors, rate limits and timeouts map onto the existing error types.
- Default model is `gemini-3.6-flash`. Older tags such as `gemini-2.5-flash`
  are still listed by `models.list()` but are no longer served to new API keys
  and fail at generation time with `404 NOT_FOUND`.
- Automatic function calling is explicitly disabled on every request, removing
  a noisy SDK warning from the logs.
- Health checks and the System Status UI now report **Gemini API** readiness
  instead of an Ollama service; the API key is never displayed or logged.
- Tests mock the Gemini client — no live API requests.
- Docker Compose drops the Ollama service; the stack is now Neo4j + the app.
- Streamlit Community Cloud is supported via a secrets-to-environment bridge
  (`nexora/ui/state.py`).
- Replaced the deprecated `use_container_width=True` on buttons and dataframes
  with `width="stretch"`; the minimum Streamlit version is now `1.48.0`.
- Fixed an unclosed `<div>` in the System status service-health rows.

### Planned
- A pluggable provider interface so Gemini and other LLMs can be swapped freely.
- Hybrid retrieval with embeddings / vector search.
- Full-text and fuzzy entity matching (Neo4j full-text indexes).
- Chunking for long documents with per-chunk citations.
- File upload ingestion (PDF, DOCX, markdown).
- Per-citation listing of every document that mentions an entity.
- Streaming answer generation in the UI.
- Configurable seed-expansion count surfaced in settings.

## [1.0.0] - 2026-09-07

Initial release of the Nexora knowledge-graph intelligence engine.

### Added
- Document ingestion: paste text or load built-in sample documents; a local
  model extracts typed entities and labelled relationships as strict JSON.
- Neo4j persistence with stable name-derived entity keys, cross-document entity
  merging, document provenance nodes, and fully parameterised Cypher.
- Multi-hop GraphRAG retrieval: keyword-to-seed discovery, relevance ranking,
  neighbourhood expansion in shortest-path order, and route-aware evidence.
- Grounded answer generation over numbered evidence with inline citations
  (`[1]`, `[2]`), verified against real sources before display.
- Streamlit interface with three views: ingest, ask, and system status
  (diagnostics, graph overview, scoped graph reset).
- Health probes for Neo4j, the Ollama service and the configured model.
- Runtime connection overrides via the sidebar (session-scoped only).
- Defensive error handling with a user-safe error taxonomy.
- Offline pytest suite (no live services required) plus ruff linting.
- Dockerfile (non-root, headless) and Docker Compose stack wiring Neo4j,
  Ollama and the app together.
- GitHub Actions CI: ruff lint, format check and tests on Python 3.10–3.12.
- Complete technical handbook under `docs/`.

### Security
- Scoped graph reset: the erase action only removes Nexora `Entity`/`Document`
  nodes and never touches unrelated data in a shared database.
- LLM output is HTML-escaped before rendering in the UI.
- Graph schema constraints created lazily and best-effort on first write.
