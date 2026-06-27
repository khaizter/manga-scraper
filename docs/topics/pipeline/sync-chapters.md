# Sync chapters pipeline

**Goal:** Download chapter page images and mark chapters as synced.

**Package:** `app/pipeline/sync_chapter/`

## Flow

```
generator (pending chapters from store)
  → extract_chapter (page data URIs via browser)
  → transform_chapter (bytes + storage paths)
  → load_success / load_failure
```

- **Work unit:** one chapter
- **Generator** reads `store.get_pending_chapters(limit)`
- **Extract** scrapes page image data URIs from the chapter reader
- **Transform** decodes data URIs into `PageUpload` payloads with precomputed storage paths; builds a `ChapterDocument` with `scrapeStatus: synced`
- **Load** calls `upload_chapter_pages()` then upserts the chapter doc

## Chapter selection

Handled by `app/pipeline/chapter_selection.py`:

1. Parent manga `scrapeStatus` must be `synced`
2. For each entry in `manga.chapters[]` (in order):
   - Missing chapter subdoc → treat as pending
   - `scrapeStatus != synced` → eligible
3. Oldest `discoveredAt` manga first; within a manga, follow `chapters[]` order

## Failure handling

On per-chapter failure, `load_failure` sets the chapter subdoc to `scrapeStatus: failed`. It is retried on the next run.

## Load

### Success (`load_success`)

Uploads page images to Storage, then upserts the chapter subdoc.

**`mangas/{slug}/chapters/{chapterNumber}`:**

```json
{
  "chapterNumber": "336-1",
  "chapterSlug": "chapter-336-1",
  "storagePaths": [
    "mangas/black-clover/chapters/336-1/0.webp",
    "mangas/black-clover/chapters/336-1/1.webp"
  ],
  "scrapeStatus": "synced",
  "lastSyncedAt": "2026-06-07T16:00:00.000Z"
}
```

The parent manga doc is not modified on chapter load.

### Failure (`load_failure`)

**`mangas/{slug}/chapters/{chapterNumber}`:**

```json
{
  "chapterNumber": "336-1",
  "chapterSlug": "chapter-336-1",
  "storagePaths": [],
  "scrapeStatus": "failed",
  "lastSyncedAt": null
}
```

Eligible for retry on the next run because `scrapeStatus != synced`.

## CLI

```powershell
python cli.py pipeline sync-chapters --limit 5 --delay 30 --dry-run --verbose
```

| Flag | Default | Purpose |
|------|---------|---------|
| `--limit` / `-n` | `10` | Max pending chapters per run |
| `--delay` | `30` | Seconds between chapter scrapes |
| `--dry-run` | off | Scrape without uploading pages |
| `--verbose` / `-v` | off | Log full chapter doc + storage paths |

Requires `PIPELINE_STORE=firestore` (transform enforces this for page uploads).

## Dry run / verbose

- **Dry run:** `[Dry run] skipped loading chapter {slug}/{number} ({n} page(s))` in `sync_chapter/load.py`
- **Verbose:** logs full `ChapterDocument` dump and storage path list

## Stats output

```json
{
  "limit": 10,
  "delaySeconds": 30,
  "dryRun": false,
  "processed": 3,
  "failed": 0,
  "skipped": 0,
  "failedChapters": [],
  "status": "completed"
}
```

**Failed chapter entry:**

```json
{
  "mangaSlug": "black-clover",
  "chapterNumber": "336-1",
  "error": "No chapter pages found"
}
```

When no work is available:

```json
{
  "limit": 10,
  "delaySeconds": 30,
  "dryRun": false,
  "processed": 0,
  "failed": 0,
  "skipped": 0,
  "message": "No pending chapters"
}
```

## Store methods

- `get_pending_chapters(limit)` — generator
- `upsert_chapter()` — load success and failure

## Storage

- `upload_chapter_pages(manga_slug, chapter_number, pages)` in `app/services/storage.py`
- Uploads use `asyncio.to_thread` to avoid blocking the async event loop (Firebase SDK is synchronous)
