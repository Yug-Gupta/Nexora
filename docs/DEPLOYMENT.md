# Deploying a Public Nexora Demo

Nexora is easy to host because inference runs through the **Google Gemini API**
rather than a local model server. You have two good options:

1. **Streamlit Community Cloud** — free, zero server management (recommended).
2. **Self-hosted VPS** — full control, Docker Compose + an HTTPS reverse proxy.

Either way you need a **Gemini API key** and a **Neo4j** database (local Docker
or a free **Neo4j AuraDB** instance).

> Never commit your API key. `.env` and `.streamlit/secrets.toml` are already
> git-ignored; keep it that way. If a key leaks, revoke it in Google AI Studio.

---

## Option 1 — Streamlit Community Cloud (free)

1. Push this repository to GitHub.
2. Sign in at <https://share.streamlit.io> and choose **New app**.
3. Select the repository, branch `main`, and main file `app.py`.
4. Under **Advanced settings → Secrets**, paste (with real values):

   ```toml
   GEMINI_API_KEY = "your_gemini_api_key_here"
   GEMINI_MODEL = "gemini-3.6-flash"

   NEO4J_URI = "neo4j+s://<your-instance-id>.databases.neo4j.io"
   NEO4J_USER = "neo4j"
   NEO4J_PASSWORD = "<your-auradb-password>"
   ```

   Create a **Neo4j AuraDB Free** instance if you do not already have a Neo4j
   database, and copy its connection URI and password.
5. Deploy and open the URL, then run **System status → Run diagnostics**.

Nexora bridges these Streamlit secrets into the environment automatically
(`nexora/ui/state.py`); no code changes are required.

### Optional — Neo4j AuraDB notes

- Use the `neo4j+s://…` URI (TLS) exactly as AuraDB shows it.
- AuraDB Free is fine for a demo; wipe the graph from the *System status* tab
  when it gets stale.

---

## Option 2 — Self-hosted VPS with Docker Compose

This runs **Neo4j + the Streamlit app** together and puts an HTTPS reverse proxy
(Caddy) with HTTP Basic Auth in front. Inference still comes from Gemini, so no
model container is needed.

```
Internet ──► Caddy (443, Basic Auth) ──► Streamlit (studio:8501) ──► Neo4j
                                                       │
                                                       └──► Google Gemini API
```

### 2.1 Choose a server

Any small Linux VPS works: **1–2 vCPU, 2–4 GB RAM, 20 GB disk**, Ubuntu
22.04/24.04. Because the model runs at Google, a tiny box is enough.

Providers: Hetzner, DigitalOcean, Vultr, Railway, Render, Fly.io, etc. If you
want HTTPS, create a DNS `A` record such as `demo.yourdomain.com → <server IP>`.

### 2.2 Connect and install Docker

```bash
ssh root@<server-ip>
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker
docker --version && docker compose version
```

### 2.3 Get the code and configure `.env`

```bash
git clone https://github.com/Yug-Gupta/Nexora.git
cd Nexora
cp .env.example .env
```

Edit `.env` and set at least:

```dotenv
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.6-flash
NEO4J_PASSWORD=choose-a-strong-password
```

> **Note:** if `.env` also contains `NEO4J_URI=bolt://127.0.0.1:7687` (for
> local `streamlit run`), override it for Compose so the app reaches the
> container:
> `NEO4J_URI=bolt://graphdb:7687 docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`

Generate a Basic Auth password hash and add the three proxy lines:

```bash
docker run --rm caddy:2 caddy hash-password --plaintext 'choose-a-strong-password'
# copy the bcrypt hash it prints
```

```dotenv
APP_DOMAIN=https://demo.yourdomain.com
AUTH_USER=admin
AUTH_HASH=$2a$14$wA...
```

> No domain? Use `APP_DOMAIN=http://<server-ip>` for plain HTTP (no TLS).

### 2.4 Start the stack

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

There is no model to pull. Check progress:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f studio
```

### 2.5 Open the firewall

The base compose file publishes Neo4j (`7474/7687`) and Streamlit (`8501`) for
local development. For a public demo only Caddy's `80/443` should be reachable:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

(If your provider has a cloud firewall, apply the same rules there.)

### 2.6 Verify the demo

1. Open `https://demo.yourdomain.com` (or `http://<server-ip>`).
2. Log in with the `AUTH_USER` / password you chose.
3. Run **System status → Run diagnostics** — Neo4j and the Gemini API should be
   healthy.
4. Ingest the three built-in sample documents, then ask a cross-document
   question such as *"Which investors back Aster Systems and what else do they
   hold?"*.

### 2.7 Updating and teardown

```bash
# Update to the latest code and rebuild
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Stop (keeps volumes)
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

# Stop and delete all demo data (Neo4j + Caddy volumes)
docker compose -f docker-compose.yml -f docker-compose.prod.yml down -v
```

Neo4j data persists in the `neo4j_data` named volume.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| "The Gemini API key is not configured" | Set `GEMINI_API_KEY` in `.env` (or Streamlit secrets) and restart. |
| "The Gemini API key was rejected" | The key is wrong/disabled — create a new one in Google AI Studio. |
| "rate limit was reached" | Free-tier quota hit; wait, or switch `GEMINI_MODEL` to a lighter model. |
| Caddy can't get a certificate | The DNS `A` record must point at this server before start; restart the `proxy` service. |
| Blank page behind the proxy | Check `docker compose … logs studio`; Streamlit must be healthy on `8501`. |
| Basic Auth not prompting | Browser cached an old session — use an incognito window. |
| Neo4j connection failure | Verify `NEO4J_URI`/credentials; AuraDB URIs start with `neo4j+s://`. |
