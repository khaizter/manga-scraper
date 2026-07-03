# manga-scraper

A web-scraping pipeline that discovers manga from [mangakakalot.gg](https://www.mangakakalot.gg), syncs metadata and chapter lists, and uploads chapter page images to Firebase. It runs locally via CLI, in Docker, and on Google Cloud Run Jobs.

## What this project does

The core of the project is a **batch ETL pipeline** — not a one-off scraper. Work flows through three stages:

```
discover  →  sync manga  →  sync chapters
```

| Stage | What it does |
|-------|----------------|
| **Discover** | Scans genre listing pages and enqueues new manga slugs as pending stubs |
| **Sync manga** | Scrapes title, author, cover, and chapter list; writes to Firestore + Storage |
| **Sync chapters** | Scrapes chapter page images and uploads them to Firebase Storage |

The `mangas` Firestore collection acts as both the **catalog** and the **work queue**. Each run is bounded by CLI flags (`--page-count`, `--limit`, etc.) so you can process data in small batches.

Scraping uses **headed Chrome** (via [pydoll](https://github.com/nicepkg/pydoll)) inside a virtual display (Xvfb). The target site uses Cloudflare and page guards, so the browser layer handles Turnstile bypass, proxy auth, and navigation retries. HTTP calls (chapter API, image downloads) can route through the same proxy when configured.

## API

There is a **FastAPI** service (`app/main.py`) with endpoints that **scrape live** from the site today:

- `POST /api/mangas` — listing page
- `GET /api/mangas/{slug}` — manga detail + chapters
- `GET /api/mangas/{slug}/chapter/{chapter_number}` — chapter pages

The API direction is still open. It may eventually **serve cached data from Firestore and Firebase Storage** (what the pipeline already writes) instead of scraping on every request. For now, treat the API as experimental — the pipeline CLI is the primary production path.

## Tech stack

- **Python 3.12** — CLI (`typer`) and API (`fastapi` + `uvicorn`)
- **Chrome + pydoll** — browser scraping
- **Firebase Admin** — Firestore (catalog/queue) and Storage (covers + chapter images)
- **aiohttp** — HTTP API and image fetches
- **Docker** — local API container and Cloud Run image
- **pytest** — unit tests

## Project layout

```
app/
  core/         # Browser, Firebase, proxy, env
  services/     # Scraping and Storage uploads
  pipeline/     # Batch ETL (discover, sync-manga, sync-chapter)
  api/          # FastAPI routes
cli.py          # CLI entry point
docs/           # Detailed docs (pipeline, CLI, architecture)
tests/          # Unit tests
credentials/    # Local secrets (gitignored) — Firebase key, Bright Data cert
```

## Dev environment setup

### Prerequisites

- **Python 3.12+**
- **Google Chrome** (for local CLI scraping outside Docker)
- **Docker Desktop** (optional — for running the API container)
- A **Firebase project** with Firestore and Storage enabled (for `PIPELINE_STORE=firestore`)

### 1. Clone and install dependencies

```powershell
git clone <repo-url>
cd manga-scraper

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt   # optional — for tests
```

### 2. Configure environment variables

```powershell
copy .env.example .env
```

Edit `.env` with your values. At minimum for Firestore:

| Variable | Purpose |
|----------|---------|
| `PIPELINE_STORE` | `json` (local files) or `firestore` (production) |
| `FIREBASE_PROJECT_ID` | Your Firebase project ID |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to Firebase Admin SDK JSON key |

For local JSON-only dev (no Firebase), set `PIPELINE_STORE=json` and skip the Firebase vars.

### 3. Add credentials

Create a `credentials/` folder (gitignored) and place files there:

```
credentials/
  your-firebase-adminsdk.json          # Firebase service account key
  brightdata/
    BrightData SSL certificate (port 33335).crt   # optional — proxy only
```

In `.env`, point to these paths:

```env
GOOGLE_APPLICATION_CREDENTIALS=C:/path/to/manga-scraper/credentials/your-firebase-adminsdk.json
FIREBASE_CREDENTIALS_CONTAINER_PATH=/app/credentials/your-firebase-adminsdk.json
```

Use **forward slashes** in `.env` paths on Windows (`\b` in `\brightdata` is interpreted as an escape).

### 4. Optional — Bright Data proxy

Omit proxy vars to connect directly (fine for local dev). For Cloud Run or when the site blocks datacenter IPs, set:

```env
CHROME_PROXY_URL=http://brd-customer-xxx-zone-isp_proxy1:password@brd.superproxy.io:33335
CHROME_PROXY_WARMUP_URL=https://geo.brdtest.com/welcome.txt?product=isp&method=native
CHROME_PROXY_CA_CERT=C:/path/to/credentials/brightdata/BrightData SSL certificate (port 33335).crt
```

If `CHROME_PROXY_URL` is set but you want a direct connection for one local run:

```powershell
python cli.py --non-proxy list --page 1
```

### 5. Run the CLI

```powershell
# One-off scrape (no Firestore)
python cli.py list --page 1
python cli.py detail black-clover

# Pipeline — dry run first (scrape only, no writes)
python cli.py pipeline discover --start-page 1 --page-count 1 --dry-run --verbose
python cli.py pipeline sync-manga --limit 1 --dry-run --verbose

# Pipeline — real writes (requires PIPELINE_STORE=firestore)
python cli.py pipeline discover --start-page 1 --page-count 3
python cli.py pipeline sync-manga --limit 5
python cli.py pipeline sync-chapters --limit 3

# Queue status
python cli.py pipeline status
```

See [docs/topics/cli/README.md](docs/topics/cli/README.md) for all commands, flags, and Cloud Run job setup.

### 6. Run the API (Docker)

```powershell
docker compose up --build
```

API: [http://localhost:8001](http://localhost:8001)  
Health: [http://localhost:8001/health](http://localhost:8001/health)

Docker mounts `./credentials` → `/app/credentials` and loads `.env` automatically.

### 7. Run tests

```powershell
python -m pytest
```

## Production (Cloud Run)

The same Docker image runs pipeline jobs on **Cloud Run Jobs** with Xvfb + Chrome. Jobs use `/job-entrypoint.sh` instead of the API entrypoint. Env vars (`PIPELINE_STORE`, `FIREBASE_PROJECT_ID`, proxy settings) are configured on each job in the GCP Console.

Cloud Run uses the service account's Application Default Credentials for Firestore — no JSON key mount needed if permissions are set correctly.

### Auto-deploy (GitHub Actions)

On every push to `main`, CI runs unit tests, then:

1. Builds the Docker image
2. Pushes to `asia-southeast1-docker.pkg.dev/mangako-91de7/manga-scraper/api` (`:latest` and `:<git-sha>`)
3. Updates all Cloud Run jobs to the new image

Workflow: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)

#### One-time setup

**1. Create a deploy service account** (GCP Console → IAM → Service Accounts):

| Role | Why |
|------|-----|
| `Artifact Registry Writer` | Push Docker images |
| `Cloud Run Admin` | Update job definitions |

Download a JSON key for this service account.

**2. Add GitHub repository secrets** (Settings → Secrets and variables → Actions):

| Secret | Value |
|--------|--------|
| `GCP_CREDENTIALS` | Full JSON contents of the deploy service account key |
| `BRIGHTDATA_CA_CERT_BASE64` | Base64-encoded Bright Data `.crt` (required for proxy in the image) |

To encode the cert on Windows PowerShell:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("credentials/brightdata/BrightData SSL certificate (port 33335).crt"))
```

**3. Push to `main`** — the deploy job runs after unit tests pass.

PRs only run unit tests; deploy is skipped until merge.

## Documentation

| Topic | Link |
|-------|------|
| CLI commands and flags | [docs/topics/cli/README.md](docs/topics/cli/README.md) |
| Pipeline overview | [docs/topics/pipeline/README.md](docs/topics/pipeline/README.md) |
| Firestore / Storage data model | [docs/topics/pipeline/data-model.md](docs/topics/pipeline/data-model.md) |
| App architecture | [docs/topics/architecture/README.md](docs/topics/architecture/README.md) |
