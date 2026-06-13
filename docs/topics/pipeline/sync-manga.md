# Sync manga pipeline

**Goal:** Enrich pending stubs with metadata, chapter list, and cover image.

**Package:** `app/pipeline/sync_manga/`

## Flow

```
generator (pending mangas from store)
  → mark processing (skipped on dry run)
  → extract_manga (detail page + chapters API in parallel)
  → transform_manga
  → load_success / load_failure
```

- **Work unit:** one manga
- **Generator** reads `store.get_pending_mangas(limit)`
- **Extract** scrapes the detail page and fetches chapter numbers via HTTP API concurrently
- **Transform** builds a full `MangaDocument` plus `ChapterDocument` stubs (`scrapeStatus: pending`, no pages yet); preserves `discoveredAt` / `createdAt` from the existing stub
- **Load** calls `upload_manga_cover()` then upserts the manga doc and all chapter stubs

## Orchestration notes

Before scrape (real runs only), the pipeline marks the manga as `processing` and sets `lastAttemptAt`.

If the run crashes catastrophically, `_reset_stuck_processing` resets any in-flight mangas back to `pending`.

## Failure handling

On per-manga failure, `load_failure`:

- Increments `attempts`
- Sets `lastError`
- Sets status back to `pending` for retry, or `failed` after `PIPELINE_MAX_RETRIES`

## Load

### Success (`load_success`)

Uploads the cover to Storage, then upserts the manga doc and one chapter stub per entry in `chapters[]`.

**`mangas/{slug}`:**

```json
{
  "slug": "black-clover",
  "title": "Black Clover",
  "description": "...",
  "author": "Yuki Tabata",
  "status": "Ongoing",
  "sourceUrl": "https://mangakakalot.gg/manga/black-clover",
  "chapters": ["1", "2", "336-1"],
  "coverStoragePath": "mangas/black-clover/cover.webp",
  "scrapeStatus": "synced",
  "discoveredAt": "2026-06-07T12:00:00.000Z",
  "attempts": 0,
  "lastAttemptAt": null,
  "lastError": null,
  "lastSyncedAt": "2026-06-07T14:30:00.000Z",
  "createdAt": "2026-06-07T12:00:00.000Z",
  "updatedAt": "2026-06-07T14:30:00.000Z"
}
```

**`mangas/{slug}/chapters/{chapterNumber}`** (one stub per chapter, written in the same load):

```json
{
  "chapterNumber": "336-1",
  "chapterSlug": "chapter-336-1",
  "storagePaths": [],
  "scrapeStatus": "pending",
  "lastSyncedAt": null
}
```

### Failure (`load_failure`)

Updates the existing manga doc — does not create chapter stubs.

**Retryable** (`attempts < PIPELINE_MAX_RETRIES`):

```json
{
  "slug": "black-clover",
  "scrapeStatus": "pending",
  "attempts": 1,
  "lastAttemptAt": "2026-06-07T14:30:00.000Z",
  "lastError": "Timeout waiting for page load"
}
```

**Permanent failure** (`attempts >= PIPELINE_MAX_RETRIES`):

```json
{
  "slug": "black-clover",
  "scrapeStatus": "failed",
  "attempts": 3,
  "lastAttemptAt": "2026-06-07T15:00:00.000Z",
  "lastError": "Timeout waiting for page load"
}
```

## CLI

```powershell
python cli.py pipeline sync --limit 10 --delay 30 --dry-run --verbose
```

| Flag | Default | Purpose |
|------|---------|---------|
| `--limit` / `-n` | `10` | Max pending mangas per run |
| `--delay` | `30` | Seconds between manga scrapes |
| `--dry-run` | off | Scrape without writing to Firestore/Storage |
| `--verbose` / `-v` | off | Log full manga doc + chapter slugs |

## Dry run / verbose

- **Dry run:** `[Dry run] skipped loading manga {slug} ({n} chapter stub(s))` in `sync_manga/load.py`
- **Verbose:** logs full `MangaDocument` dump and chapter slug list

## Stats output

```json
{
  "processed": 8,
  "failed": 2,
  "skipped": 0,
  "failedSlugs": [
    { "slug": "some-manga", "error": "Timeout waiting for page load" }
  ],
  "status": "partially_completed"
}
```

When no work is available:

```json
{ "processed": 0, "failed": 0, "skipped": 0, "message": "No pending mangas" }
```

## Store methods

- `get_pending_mangas(limit)` — generator
- `upsert_manga()` — load success and failure
- `upsert_chapter()` — load success (chapter stubs)

## Storage

- `upload_manga_cover(slug, data_uri)` in `app/services/storage.py`
