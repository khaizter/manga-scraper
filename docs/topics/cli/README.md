# CLI commands

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
| `CHROME_PAGE_GUARD_WAIT` | `60` | Seconds to wait after Cloudflare click |

## Common flags

| Flag | Use on |
|------|--------|
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
