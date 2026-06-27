# Discover pipeline

**Goal:** Find new manga slugs from genre listing pages and enqueue them as pending stubs.

**Package:** `app/pipeline/discover/`

## Flow

```
generator (listing pages)
  → transform_page
  → load_batch → store.enqueue_slugs()
```

- **Work unit:** one listing page → many slugs
- **Generator** walks pages from `start_page` to `end_page`; extract runs inside the generator
- **Load** creates `MangaDocument.pending_stub(slug)` for slugs not already in the store (skips existing non-failed entries)
- Failed pages are recorded in `failedPages`; other pages continue

## Load

Writes one pending manga stub per new slug to `mangas/{slug}`.

**Example document** (`load_batch` → `enqueue_slugs`):

```json
{
  "slug": "black-clover",
  "title": null,
  "description": null,
  "author": null,
  "status": null,
  "sourceUrl": null,
  "chapters": [],
  "coverStoragePath": null,
  "scrapeStatus": "pending",
  "discoveredAt": "2026-06-07T12:00:00.000Z",
  "attempts": 0,
  "lastAttemptAt": null,
  "lastError": null,
  "lastSyncedAt": null,
  "createdAt": "2026-06-07T12:00:00.000Z",
  "updatedAt": "2026-06-07T12:00:00.000Z"
}
```

Slugs that already exist with a non-`failed` status are skipped and not overwritten.

## CLI

```powershell
python cli.py pipeline discover --start-page 1 --page-count 3 --delay 2 --dry-run --verbose
```

| Flag | Default | Purpose |
|------|---------|---------|
| `--start-page` | `1` | First listing page to scan |
| `--page-count` / `-n` | `1` | Number of listing pages |
| `--delay` | `2` | Seconds between page navigations |
| `--dry-run` | off | Scrape without enqueueing stubs |
| `--verbose` / `-v` | off | Log full slug array per page |

## Dry run / verbose

- **Dry run:** `[Dry run] skipped loading N slug(s)` in `discover/load.py`
- **Verbose:** logs page number, slug count, full slug array, and enqueued count

## Stats output

```json
{
  "startPage": 1,
  "pageCount": 3,
  "endPage": 3,
  "delaySeconds": 2,
  "dryRun": false,
  "discovered": 120,
  "enqueued": 45,
  "pagesSucceeded": 3,
  "pagesFailed": 0,
  "failedPages": [],
  "status": "completed"
}
```

**Failed page entry:**

```json
{ "page": 2, "error": "No manga slugs found on page" }
```

## Store methods

- `enqueue_slugs(slugs)` — called by `load_batch`
