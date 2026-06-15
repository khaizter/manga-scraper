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

Set store for real writes:

```powershell
$env:PIPELINE_STORE = "firestore"
```

Local JSON store (default, no Firebase):

```powershell
$env:PIPELINE_STORE = "json"
```

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
