# Deploying a Public Nexora Demo

This guide turns your local Nexora into a **public, always-on demo** you can
link from a resume or portfolio. It reuses the exact stack you already run
locally — **no application code changes** — and adds an HTTPS reverse proxy
with HTTP Basic Auth in front of it.

```
Internet ──► Caddy (443, Basic Auth) ──► Streamlit (studio:8501) ──► Neo4j + Ollama
```

> Short version: rent an 8 GB VPS, install Docker, clone the repo, add three
> lines to `.env`, and run two `docker compose` commands.

---

## 1. Choose a server

Any small Linux VPS works. Recommended minimum: **2 vCPU, 8 GB RAM, 40 GB SSD**,
Ubuntu 22.04/24.04.

- 8 GB gives Neo4j (~1–2 GB) and a small Ollama model such as `llama3.2`
  (~2 GB) comfortable headroom.
- Providers: Hetzner, DigitalOcean, Vultr, Railway, Render, Fly.io, etc.
- Optional but recommended: create a DNS `A` record such as
  `demo.yourdomain.com → <server IP>` before starting (needed for HTTPS).

## 2. Connect and install Docker

```bash
ssh root@<server-ip>
```

Install Docker Engine + Compose plugin (official convenience script, or follow
the [Docker docs](https://docs.docker.com/engine/install/)):

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker
```

Verify:

```bash
docker --version
docker compose version
```

## 3. Get the code and configure `.env`

```bash
git clone https://github.com/Yug-Gupta/Nexora.git
cd Nexora
cp .env.example .env
```

Generate a Basic Auth password hash and add the three lines below to `.env`
(the file is already git-ignored, so secrets never get committed):

```bash
docker run --rm caddy:2 caddy hash-password --plaintext 'choose-a-strong-password'
# -> copies a bcrypt hash like $2a$14$wA...  (write it down)
```

Append to `.env`:

```dotenv
# --- Public demo (Caddy) -----------------------------------------------------
APP_DOMAIN=https://demo.yourdomain.com
AUTH_USER=admin
AUTH_HASH=$2a$14$wA...
```

> No domain yet? Point `APP_DOMAIN` at the bare server IP with plain HTTP:
> `APP_DOMAIN=http://203.0.113.10`. Skip step 5's DNS requirement in that case.

## 4. Start the stack

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Wait for everything to become healthy, then install the model used by the app:

```bash
docker exec nexora-ollama ollama pull llama3.2
```

> Prefer a faster/smaller model? Edit `OLLAMA_MODEL` in the `studio` service of
> `docker-compose.yml` (e.g. `qwen2.5:3b`) and pull that tag instead. The
> default `llama3.2` is ~2 GB and runs well on 8 GB.

Inspect progress:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f studio
```

## 5. Open the firewall

The base compose file publishes several ports for **local development**
(Neo4j `7474/7687`, Ollama `11434`, Streamlit `8501`). For a public demo only
Caddy's `80/443` should be reachable — block the rest so the database and model
server are never exposed.

With UFW:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

If your provider has a cloud firewall, apply the same rules there instead
(allow only 22, 80, 443).

## 6. Verify the demo

1. Open `https://demo.yourdomain.com` (or `http://<server-ip>`).
2. Log in with the `AUTH_USER` / password you chose.
3. On **System status**, run *Diagnostics* — Neo4j, Ollama and the model should
   all report healthy.
4. Ingest the three built-in sample documents, then ask a cross-document
   question such as *"Which investors back Aster Systems and what else do they
   hold?"* to prove multi-hop retrieval works.

## 7. Keeping it running and updating

```bash
# Inspect logs / restart a service
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f --tail=200

# Update to the latest code and rebuild
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Full teardown (keeps volumes)
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

# Teardown INCLUDING all demo data (Neo4j + Ollama + Caddy volumes)
docker compose -f docker-compose.yml -f docker-compose.prod.yml down -v
```

Neo4j and Ollama data persist in named volumes (`neo4j_data`, `ollama_data`).
Back them up by snapshotting `/var/lib/docker/volumes/` or use your provider's
volume/disk snapshots.

## 8. Troubleshooting

| Symptom | Fix |
| --- | --- |
| Caddy can't get a certificate | The DNS `A` record must point at this server before start; then `docker compose ... restart proxy`. |
| Model answers are slow | First request loads the model into RAM. Pre-warm by sending one ingest/answer, then retry. |
| App reachable, but blank page | Check `docker compose ... logs studio`; ensure the proxy is healthy. |
| Basic Auth not prompting | The browser may have cached an old session — open an incognito window. |
| Out of memory / Neo4j restart loops | Use a 4 GB-model-free setup: pull a smaller model, or raise the VPS to 8 GB. |

## 9. Making the demo public without a password (optional)

If you prefer interviewers to click straight in, remove the `basic_auth` block
from `deploy/Caddyfile` and restart the proxy. **Warning:** anyone with the URL
could then also erase the graph from the *System status* tab, so either clear
the graph and re-ingest the samples beforehand, or keep Basic Auth and print
the credentials next to the demo link on your resume.
