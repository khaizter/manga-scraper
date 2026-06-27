# CLI commands

Global options apply to every command (place **before** the subcommand):

```powershell
python cli.py --non-proxy list --page 1
python cli.py --non-proxy pipeline discover --dry-run
```

```powershell
python cli.py ...
```

## One-off scrape (no Firestore)

```powershell
# Listing page
python cli.py list --page 1

# Manga detail + chapter list
python cli.py detail black-clover

# Chapter pages (data URIs)
python cli.py chapter black-clover chapter-336-1
```

When `CHROME_PROXY_URL` is set in `.env` but you want to test locally without proxy usage, prefix with `--non-proxy` (see [Optional proxy](#optional-proxy-bright-data-isp)).

## Pipeline

Docker loads `.env` via `env_file` in `docker-compose.yml`

Set store for real writes (also in `.env`):

```powershell
$env:PIPELINE_STORE = "firestore"
```

Local JSON store (default if unset):

```powershell
$env:PIPELINE_STORE = "json"
```

Docker also mounts `./credentials` → `/app/credentials` for Firebase. Set `FIREBASE_CREDENTIALS_CONTAINER_PATH` in `.env` to the in-container JSON path.

### Discover

```powershell
# Dry run — scrape only, no writes
python cli.py pipeline discover --start-page 1 --page-count 1 --dry-run --verbose

# Enqueue pending stubs
python cli.py pipeline discover --start-page 1 --page-count 3 --delay 2
```

### Sync manga

```powershell
# Dry run
python cli.py pipeline sync-manga --limit 1 --dry-run --verbose

# Sync 5 pending mangas
python cli.py pipeline sync-manga --limit 5 --delay 30
```

### Sync chapters

Requires `PIPELINE_STORE=firestore`.

```powershell
# Dry run
python cli.py pipeline sync-chapters --limit 1 --dry-run --verbose

# Sync 3 chapters
python cli.py pipeline sync-chapters --limit 3 --delay 30
```

### Status

```powershell
python cli.py pipeline status
```

### Cloudflare Turnstile (optional env)

If the checkbox DOM changes, override selectors (comma-separated, tried in order):

```powershell
$env:CHROME_CLOUDFLARE_CHECKBOX_SELECTORS = 'input[type="checkbox"],label'
python cli.py list --page 1
```

Prefer stable selectors like `input[type="checkbox"]` over obfuscated classes (e.g. `CDDrW6`).

After navigation, the scraper logs **page guard** status (site logo + listing selectors):

```
Page guard passed — logo=True (div.top-logo) listing=True (...) cloudflare_challenge=False url=...
Page guard failed — logo=False ... cloudflare_challenge=True ...
```

Optional env:

| Variable | Default | Purpose |
|----------|---------|---------|
| `CHROME_PAGE_GUARD_LOGO_SELECTOR` | `div.top-logo` | Site loaded indicator |
| `CHROME_PAGE_GUARD_LISTING_SELECTOR` | `div.comic-list div.list-comic-item-wrap` | Listing ready indicator |
| `CHROME_CLOUDFLARE_POST_CLICK_WAIT` | `3` | Pause after clicking Turnstile |
| `CHROME_CLOUDFLARE_RENDER_WAIT` | `3` | Wait for Turnstile widget to render in iframe |
| `CHROME_CLOUDFLARE_RETRIES` | `3` | Bypass attempts per navigation |
| `CHROME_PAGE_GUARD_WAIT` | `60` | Seconds to wait after Cloudflare click |
| `CHROME_NAVIGATE_TIMEOUT` | `300` | Max seconds for navigation through proxy |

### Optional proxy (Bright Data ISP)

Omit to scrape without a proxy (default). Use your **ISP zone** credentials from the Bright Data dashboard (port **33335**, same SSL cert):

```env
CHROME_PROXY_URL=http://brd-customer-xxx-zone-isp_proxy1:password@brd.superproxy.io:33335
CHROME_PROXY_WARMUP_URL=https://geo.brdtest.com/welcome.txt?product=isp&method=native
CHROME_PROXY_CA_CERT=C:/path/to/credentials/brightdata/BrightData SSL certificate (port 33335).crt
```

The `.crt` is **loaded from file** at runtime (like `curl --cacert`), not installed to the OS. Use forward slashes in paths on Windows.

**Local testing without proxy usage:** if `CHROME_PROXY_URL` is set in `.env` (e.g. for Cloud Run parity) but you want direct connections from the CLI, pass `--non-proxy` before the subcommand. This disables proxy for both Chrome (`--proxy-server`) and HTTP image downloads (aiohttp) for that run only — your `.env` stays unchanged.

```powershell
python cli.py --non-proxy list --page 1
python cli.py --non-proxy detail black-clover
python cli.py --non-proxy pipeline sync-manga --limit 1 --dry-run
```

Docker/Cloud Run: the Bright Data `.crt` is copied into the image at build time (`credentials/brightdata/` → `/app/credentials/brightdata/`). Set `CHROME_PROXY_CA_CERT` to the in-container path, or rely on auto-discovery if the file is present.

For Cloud Run jobs, also set `CHROME_PROXY_URL`, `CHROME_PROXY_WARMUP_URL`, and `PIPELINE_STORE=firestore`.

Logs show `Using Chrome proxy host:port` (credentials are not logged).

For Cloud Run jobs, add `CHROME_PROXY_URL`, `CHROME_PROXY_CA_CERT`, and optionally `CHROME_PROXY_WARMUP_URL` on the job configuration.

## Common flags

| Flag | Use on |
|------|--------|
| `--non-proxy` | **All commands** — connect directly; ignore `CHROME_PROXY_URL` for this run |
| `--dry-run` | pipeline discover / sync-manga / sync-chapters |
| `--verbose` / `-v` | pipeline discover / sync-manga / sync-chapters |
| `--limit` / `-n` | pipeline sync-manga, sync-chapters |
| `--page-count` / `-n` | pipeline discover |

## Help

```powershell
python cli.py --help
python cli.py pipeline --help
python cli.py pipeline sync-manga --help
```
