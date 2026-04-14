# FortiDLP Agent

Lightweight AI agent that answers natural-language operational questions about a
FortiDLP tenant, plus a dropdown of canned queries for common day-to-day checks
(top users, policy hits, unhealthy devices, license usage, OS breakdown).

- **LLM:** Anthropic Claude (`claude-sonnet-4-5`) via tool-use
- **Backend:** FastAPI (Python 3.11+)
- **UI:** single-page HTML/JS, served by FastAPI on `localhost:8000`
- **FortiDLP access:** read-only bearer token from `.env`
- **Packaging:** Docker + docker-compose

## Run locally (native)

```bash
python -m venv .venv
. .venv/Scripts/activate          # Windows; Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env              # fill in ANTHROPIC_API_KEY, FORTIDLP_BASE_URL, FORTIDLP_TOKEN
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000.

## Run locally (Docker)

```bash
cp .env.example .env              # fill in values
docker compose up --build
```

## Tests

```bash
pytest
ruff check .
```

## Portability

- **GitHub:** push this directory, CI (`.github/workflows/ci.yml`) runs lint + tests.
- **Any Linux server:** `git clone && docker compose up -d`.
- **Kubernetes:** image is container-ready; add Deployment + Secret manifests when a
  target cluster is chosen.

## Security notes

- Use a **read-only** FortiDLP API token. Never reuse an admin token.
- `.env` is gitignored. Never commit tokens.
- Every tool invocation is logged to stdout (tool name + args, never the token).
- The FortiDLP client wrapper is strictly read-only — no `POST`/`PUT`/`DELETE`.
