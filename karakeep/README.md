# Karakeep

Self-hosted Karakeep (formerly Hoarder) behind Caddy.

This stack:

- joins the external Docker network `caddy-network`
- does not publish ports to the host
- expects your reverse proxy to route to `karakeep:3000`

## Prerequisites

- Docker Engine + Docker Compose v2 (`docker compose`)
- External network `caddy-network` (one-time):

```bash
docker network inspect caddy-network >/dev/null 2>&1 || docker network create caddy-network
```

## Quick Start

```bash
cp .env.example .env
$EDITOR .env
docker compose up -d
docker compose logs -f
```

### Generate Secrets

```bash
# NEXTAUTH_SECRET
openssl rand -base64 36

# MEILI_MASTER_KEY (alphanumeric only)
openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 48; echo
```

## Configuration Guidelines

- Set `NEXTAUTH_URL` to your public HTTPS URL (the same domain Caddy serves).
- Keep `NEXTAUTH_SECRET` and `MEILI_MASTER_KEY` long and random.
- For public instances, keep `DISABLE_SIGNUPS=true` and use the admin bootstrap flow below.
- For OpenAI itself, set `OPENAI_API_KEY` and usually leave `OPENAI_BASE_URL` unset.
- For OpenAI-compatible gateways (LiteLLM/OpenRouter/Azure), set both `OPENAI_API_KEY` and `OPENAI_BASE_URL` (usually ending with `/v1`).
- After editing `.env`, apply changes with `docker compose up -d`.

## Reverse Proxy (Caddy)

Example Caddyfile snippet:

```caddy
karakeep.example.com {
  reverse_proxy karakeep:3000
}
```

## Admin Bootstrap (When Signups Are Disabled)

If you run with `DISABLE_SIGNUPS=true` and there are no users yet, you need to
bootstrap the first admin account:

```bash
# 1) Temporarily allow signups
sed -i 's/^DISABLE_SIGNUPS=.*/DISABLE_SIGNUPS=false/' .env
docker compose up -d

# 2) Create the first user via the web UI (it becomes Admin automatically)

# 3) Disable signups again
sed -i 's/^DISABLE_SIGNUPS=.*/DISABLE_SIGNUPS=true/' .env
docker compose up -d
```

Security note: don't leave signups open on a public domain; whoever creates the
first account becomes the Admin.

## Invites (Email / Link)

Karakeep can send invitation emails, but only if you configure SMTP (`SMTP_*`).
If SMTP is not configured, an invite can still be created, but no email will be
delivered.

### SMTP (Recommended)

Set SMTP variables in `.env`, then apply the updated configuration:

```dotenv
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_SECURE=false
SMTP_USER=your_smtp_username
SMTP_PASSWORD=your_smtp_password
SMTP_FROM="Karakeep <no-reply@example.com>"
```

```bash
docker compose up -d
docker compose logs -f karakeep
```

### Manual Invite Link (No SMTP)

Invite accept URL format:

```text
https://<your-domain>/invite/<token>
```

If the UI doesn't show the link directly, you can fetch the token from the
SQLite DB and share the URL manually. Treat invite tokens as secrets.

```bash
python3 - <<'PY'
import sqlite3
PUBLIC_URL = "https://karakeep.example.com"
con = sqlite3.connect(".karakeep/data/db.db")
cur = con.cursor()
cur.execute("select email, token, createdAt, usedAt from invites order by createdAt desc limit 20")
for email, token, createdAt, usedAt in cur.fetchall():
    status = "used" if usedAt else "unused"
    print(f"{email}\t{status}\t{PUBLIC_URL}/invite/{token}")
con.close()
PY
```

## Data Persistence / Backups

Host paths (in this directory):

- `./.karakeep/data/` (SQLite DB + assets; this is the most important backup)
- `./.karakeep/meilisearch/` (search index; can be rebuilt if lost)

## Notes

- Full-text search requires Meilisearch; it is included in this compose file.
- Crawling/screenshotting requires headless Chrome; it is included in this
  compose file.
- AI tagging (automatic tagging) and AI summarization are optional. They are
  enabled only when an inference provider is configured.

## LLM (Auto Tagging / Summaries)

Karakeep can run background inference jobs to:

- auto-tag bookmarks (default enabled when configured)
- auto-summarize bookmarks (default disabled)

### Option A: OpenAI

Add at least this line to `.env` to enable inference (the AI Settings menu will
appear in the UI), and new bookmarks will start getting auto-tagged in the
background.

```bash
OPENAI_API_KEY=sk-...
```

If you are using OpenAI itself, you typically do not need `OPENAI_BASE_URL`.

Optional (defaults shown):

```bash
# Models
INFERENCE_TEXT_MODEL=gpt-4.1-mini
INFERENCE_IMAGE_MODEL=gpt-4o-mini

# Language for generated tags/summaries
INFERENCE_LANG=english

# Auto behaviors
INFERENCE_ENABLE_AUTO_TAGGING=true
INFERENCE_ENABLE_AUTO_SUMMARIZATION=false
```

Apply:

```bash
docker compose up -d
docker compose logs -f karakeep | grep -Ei 'inference|tag|summar' || true
```

Adjust in the UI:

- `User Settings -> AI Settings`: per-user auto-tagging/auto-summarization on/off, language, extra prompt instructions
- Admin tools: `/admin/admin_tools` for per-bookmark `Re-tag`, `Resummarize`

### Option A2: OpenAI-Compatible API (LiteLLM, OpenRouter, Azure, etc.)

If you use an OpenAI-compatible gateway/proxy, set `OPENAI_BASE_URL` to that
endpoint. Most compatible servers expect the `/v1` suffix.

```bash
# Example: LiteLLM running on a Docker network
OPENAI_API_KEY=your_litellm_key_or_dummy
OPENAI_BASE_URL=http://litellm:4000/v1
```

Notes:

- `OPENAI_API_KEY` must be set even if your proxy doesn't require it, because
  Karakeep uses it to decide whether inference is configured. If your proxy
  ignores the key, you can use a dummy value.
- Model names depend on your proxy. Set `INFERENCE_TEXT_MODEL` /
  `INFERENCE_IMAGE_MODEL` to whatever your proxy exposes (often the upstream
  model name, or a proxy-specific alias).

### Option B: Ollama (Local, Recommended: OpenAI-compatible API)

For example, if an Ollama container named `ollama` shares the `caddy-network` network with Karakeep:

```bash
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://ollama:11434/v1

# Example models (pull them in Ollama first)
INFERENCE_TEXT_MODEL=gemma3
INFERENCE_IMAGE_MODEL=llava
```

Alternative (native Ollama API): set `OLLAMA_BASE_URL=http://ollama:11434` and
make sure `OPENAI_API_KEY` is NOT set (OpenAI config takes precedence).

### Common Toggles

```bash
# Tag language
INFERENCE_LANG=korean

# Enable auto summarization
INFERENCE_ENABLE_AUTO_SUMMARIZATION=true
```

Apply changes:

```bash
docker compose up -d
docker compose logs -f karakeep | grep -Ei 'inference|tag|summar' || true
```

## References

- Docs: https://docs.karakeep.app/installation/docker/
