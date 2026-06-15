# App layer hierarchy

How `core/`, `services/`, and `pipeline/` relate — and where persistence, scraping, and orchestration live.

## Overview

```
┌─────────────────────────────────────────────────────────┐
│  Entry points: cli.py, app/main.py (API)              │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│  pipeline/          Batch ETL + domain store + models   │
│  (orchestration, queue queries, document shapes)        │
└───────────────┬─────────────────────┬───────────────────┘
                │                     │
┌───────────────▼──────────┐  ┌───────▼───────────────────┐
│  services/               │  │  core/                   │
│  Scraping + Storage      │  │  Infrastructure          │
│  (stateless operations)  │  │  (clients, config, env)  │
└───────────────┬──────────┘  └──────────────────────────┘
                │
                └──────────────────► core/
```

**Dependency rule:** outer layers call inward. `core/` never imports from `services/` or `pipeline/`. `services/` does not import from `pipeline/` (with one practical exception today: `storage.py` imports path helpers from `pipeline/models.py`).

## Layer responsibilities

| Layer | Path | Role | Knows about business rules? |
|-------|------|------|-----------------------------|
| **Core** | `app/core/` | App-wide infrastructure — Firebase client init, browser setup, env, shared config | No |
| **Services** | `app/services/` | Operations against external systems — scrape pages, call APIs, upload blobs | Minimal (scraping only) |
| **Pipeline** | `app/pipeline/` | Batch ETL, catalog documents, queue/persistence for the scraper | Yes |

## Core — infrastructure only

**Purpose:** “How do we connect?” — not “what do we store?” or “what work is pending?”

| Module | Responsibility |
|--------|----------------|
| `firebase.py` | Initialize Firebase Admin, expose `get_firestore_client()` and `get_storage_bucket()` |
| `browser.py` | Chrome / pydoll setup, navigation helpers |
| `config.py` | Site URLs, scrape timeouts |
| `env.py` | Load `.env` |

Core modules are **domain-free**. They should not reference `scrapeStatus`, manga slugs as queue items, or pipeline config.

```python
# core/firebase.py — thin client access
db = get_firestore_client()
bucket = get_storage_bucket()
```

## Services — stateless external operations

**Purpose:** “Do one thing against the outside world” — scrape, fetch, upload bytes — without owning catalog state or queue logic.

| Module | Responsibility |
|--------|----------------|
| `manga.py` | Scrape manga detail from the browser |
| `manga_chapter.py` | Scrape chapter page images |
| `manga_list.py` | Scrape listing page slugs |
| `chapters_api.py` | HTTP fetch for chapter numbers |
| `storage.py` | Upload cover/pages to Firebase Storage |

Services are used by:

- **CLI one-off commands** (`cli.py list`, `detail`, `chapter`)
- **Pipeline extract/load stages** (e.g. `extract_manga` → `services/manga.py`, load → `services/storage.py`)

Services do **not** decide which mangas are pending, how retries work, or how chapters are ordered in the queue. They receive inputs (a slug, a data URI, a list of page bytes) and return outputs.

## Pipeline — batch ETL and domain persistence

**Purpose:** “Run bounded batch jobs that fill the catalog” — discover → sync manga → sync chapters.

### ETL packages

Each pipeline under `discover/`, `sync_manga/`, `sync_chapter/` follows the same shape:

```
generator → extract → transform → load
```

See [pipeline/README.md](./pipeline/README.md) for the ETL pattern.

### Domain models (`pipeline/models.py`)

Pydantic documents that define the Firestore/Storage shape:

- `MangaDocument`, `ChapterDocument`
- `ScrapeStatus`, storage path helpers
- Factory methods like `MangaDocument.pending_stub()` and `from_scrape()`

These are **pipeline catalog models** — they describe what gets persisted, not how scraping works.

### Domain store (`pipeline/store.py`)

**`MangaStore` is domain-specific persistence and queue access for the pipeline.** It is not generic Firestore CRUD.

It exposes operations that encode pipeline business rules:

| Method | Domain meaning |
|--------|----------------|
| `enqueue_slugs()` | Discover: create pending stubs, skip existing non-failed |
| `get_pending_mangas(limit)` | Sync manga: query by `scrapeStatus`, respect retry limits, sort by priority |
| `get_pending_chapters(limit)` | Sync chapters: synced mangas only, chapter order, selection rules |
| `upsert_manga()` / `upsert_chapter()` | Write catalog documents after load |
| `count_scrape_status()` | Status command aggregates |

Two implementations share the same interface:

- **`FirestoreStore`** — production; uses `core/firebase.py` + Firestore queries
- **`JsonFileStore`** — local dev; mirrors document shape under `data/pipeline/mangas/`

Switch via `PIPELINE_STORE=json|firestore`.

```python
# pipeline/store.py — domain query, not generic CRUD
query = collection.where('scrapeStatus', '==', status.value)
# + filter attempts < PIPELINE_MAX_RETRIES
# + sort by discoveredAt
```

That logic belongs here — not in `core/` or generic `services/firebase/` helpers — because it defines **what the pipeline considers work**.

### Other pipeline modules

| Module | Role |
|--------|------|
| `runner.py` | Thin facade; wires CLI to pipeline classes |
| `config.py` | Pipeline env defaults (`PIPELINE_DELAY_SECONDS`, etc.) |
| `chapter_selection.py` | Rules for which chapters are eligible |
| `types.py` | Shared `PipelineOptions` (`dry_run`, `verbose`, `delay`) |

## How a sync manga run uses the layers

```
cli.py
  → PipelineRunner                    (pipeline/runner.py)
    → SyncMangaPipeline.run()           (pipeline/sync_manga/pipeline.py)
      → generator                       (pipeline/store.py — get_pending_mangas)
      → extract_manga                   (services/manga.py + services/chapters_api.py)
      → transform_manga                 (pipeline/models.py — pure)
      → load_success                    (services/storage.py + pipeline/store.py)
```

- **Store** answers: “which mangas should I process?”
- **Services** answer: “what did the site return for this slug?”
- **Storage service** answer: “upload this cover blob”
- **Store again** answer: “persist the enriched document”

## What goes where — quick reference

| Question | Layer |
|----------|-------|
| Initialize Firebase SDK? | `core/firebase.py` |
| Navigate Chrome to a URL? | `core/browser.py` |
| Scrape one manga’s detail page? | `services/manga.py` |
| Upload bytes to a Storage path? | `services/storage.py` |
| Define `scrapeStatus` and document fields? | `pipeline/models.py` |
| Query pending mangas for the queue? | `pipeline/store.py` |
| Loop extract → transform → load? | `pipeline/*/pipeline.py` |

## Related docs

- [Pipeline pattern](./pipeline/README.md) — ETL stages, props, CLI
- [Data model](./pipeline/data-model.md) — Firestore and Storage document shapes
