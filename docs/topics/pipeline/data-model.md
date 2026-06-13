# Pipeline data model

Firestore documents and Firebase Storage paths used across all pipelines.

## Firestore

### `mangas/{slug}`

Catalog document and queue stub. Discover creates a minimal stub; sync manga enriches it.

| Field | Notes |
|-------|-------|
| `slug` | Document ID |
| `title`, `description`, `author`, `status` | Filled by sync manga |
| `sourceUrl` | Manga page URL |
| `chapters` | Ordered chapter numbers (e.g. `"336-1"`) |
| `coverStoragePath` | Storage path to cover — never base64 |
| `scrapeStatus` | `pending` → `processing` → `synced` (or `failed`) |
| `discoveredAt`, `createdAt`, `updatedAt` | Timestamps |
| `attempts`, `lastError`, `lastAttemptAt` | Retry tracking (sync manga) |
| `lastSyncedAt` | Set when manga sync completes |

### `mangas/{slug}/chapters/{chapterNumber}`

| Field | Notes |
|-------|-------|
| `chapterNumber` | Document ID (e.g. `"336-1"`) |
| `chapterSlug` | URL slug for scraping (e.g. `"chapter-336-1"`) |
| `storagePaths` | Ordered Storage paths to page images |
| `scrapeStatus` | `pending` → `synced` (or `failed`) |
| `lastSyncedAt` | Set when chapter sync completes |

Never store image bytes or data URIs in Firestore (1 MB document limit).

## Firebase Storage

Default bucket: `{projectId}.firebasestorage.app`

```
mangas/{slug}/cover.{ext}
mangas/{slug}/chapters/{chapterNumber}/{pageIndex}.{ext}
```

- `ext`: `jpg`, `png`, `webp`, or `gif` (from source mime type)
- `pageIndex`: 0-based, matches order in `storagePaths`

Example:

```
mangas/black-clover/cover.webp
mangas/black-clover/chapters/336-1/0.webp
mangas/black-clover/chapters/336-1/1.webp
```

## Status lifecycle

```
Discover          → scrapeStatus: pending
Sync manga        → pending/processing → synced (+ chapter stubs: pending)
Sync chapters     → chapter pending/failed → synced
```

App-facing reads should filter out documents where `scrapeStatus != synced`.

## Code references

- Document models: `app/pipeline/models.py`
- Path helpers: `manga_cover_storage_path()`, `chapter_page_storage_path()`
- Uploads: `app/services/storage.py`
