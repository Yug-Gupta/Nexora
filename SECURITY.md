# Security

Nexora is a **local-first** application: documents, the knowledge graph and the
LLM all run on your own machine or a private network. This page summarises the
security posture and how to report a problem.

## Reporting a vulnerability

If you find a security issue in Nexora, please **do not open a public issue
with exploit details**. Instead:

1. Open a [private security advisory](https://github.com/Yug-Gupta/Nexora/security/advisories/new)
   on GitHub, or
2. Open a regular issue that describes the area affected **without** including
   credentials, live data or exploit code.

We treat reports seriously and will acknowledge them as soon as possible.

## Security notes

- **Credentials never live in code.** All secrets arrive via environment
  variables or a local `.env` file that is git-ignored; `.env.example` holds
  placeholders only.
- **Database credentials are never logged.** Logs refer to services and labels,
  never passwords or document bodies.
- **Cypher is fully parameterised.** The only interpolated query value is a
  validated integer depth bound.
- **LLM output is escaped.** Model and user text is HTML-escaped before it is
  rendered in the UI, preventing markup injection.
- **Scoped reset.** The "erase the graph" action removes only Nexora
  `Entity`/`Document` nodes; unrelated data in a shared database is left intact.
- **No built-in multi-user auth.** Streamlit provides no user model. For
  anything beyond a trusted network, put the app behind an authenticated
  reverse proxy.

## Local deployment checklist

- Replace the example Neo4j credentials used by `docker-compose.yml`.
- Keep `.env` out of version control (it already is via `.gitignore`).
- Use a dedicated Neo4j database for Nexora where possible.
