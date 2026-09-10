# Security

Nexora stores its knowledge graph in your own Neo4j database but sends document
text and questions to the **Google Gemini API** for extraction and answering.
Secrets (the Gemini API key and the Neo4j password) are provided through the
environment or Streamlit secrets and are never written into the repository.
This page summarises the security posture and how to report a problem.

## Reporting a vulnerability

If you find a security issue in Nexora, please **do not open a public issue
with exploit details**. Instead:

1. Open a [private security advisory](https://github.com/Yug-Gupta/Nexora/security/advisories/new)
   on GitHub, or
2. Open a regular issue that describes the area affected **without** including
   credentials, live data or exploit code.

We treat reports seriously and will acknowledge them as soon as possible.

## Security notes

- **Secrets never live in code.** The Gemini API key and Neo4j password arrive
  via environment variables, a git-ignored `.env` file, or Streamlit secrets;
  `.env.example` holds placeholders only.
- **The API key is never logged or displayed.** The Gemini gateway logs only
  whether a key is present; health checks and error messages never echo the key
  or its length.
- **Database credentials are never logged.** Logs refer to services and labels,
  never passwords or document bodies.
- **Cypher is fully parameterised.** The only interpolated query value is a
  validated integer depth bound.
- **Model output is escaped.** Model and user text is HTML-escaped before it is
  rendered in the UI, preventing markup injection.
- **Scoped reset.** The "erase the graph" action removes only Nexora
  `Entity`/`Document` nodes; unrelated data in a shared database is left intact.
- **No built-in multi-user auth.** Streamlit provides no user model. For a
  public demo, use an authenticated reverse proxy (see `docs/DEPLOYMENT.md`) or
  Streamlit Cloud's app privacy controls.

## Deployment checklist

- Create a dedicated Gemini API key for the deployment and be ready to revoke
  it if it leaks.
- Never commit `.env` or `.streamlit/secrets.toml` (both are git-ignored).
- Replace the example Neo4j credentials used by `docker-compose.yml`.
- Use a dedicated Neo4j database (or AuraDB instance) for Nexora where possible.
- Firewall a self-hosted VPS so only `22/80/443` are reachable.
