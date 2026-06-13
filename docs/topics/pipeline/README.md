# Pipeline pattern

The manga-scraper batch system is built as independent **ETL pipelines** that share a common structure, store layer, and CLI entry point. Each pipeline scrapes data from the site, shapes it into Firestore/Storage documents, and persists it in bounded batches controlled by CLI props.

## Pipelines

Three pipelines run in sequence. Each has its own doc with goals, flow, CLI flags, and stats output:

| Pipeline | Doc | CLI command |
|----------|-----|-------------|
| Discover | [discover.md](./discover.md) | `python cli.py pipeline discover` |
| Sync manga | [sync-manga.md](./sync-manga.md) | `python cli.py pipeline sync` |
| Sync chapters | [sync-chapters.md](./sync-chapters.md) | `python cli.py pipeline sync-chapters` |

Shared data shapes and Storage layout: [data-model.md](./data-model.md)

```
discover  →  sync manga  →  sync chapters
```

The `mangas` Firestore collection acts as both the catalog and the work queue.

## Architecture

```
cli.py
  └── PipelineRunner (app/pipeline/runner.py)
        ├── DiscoverPipeline
        ├── SyncMangaPipeline
        └── SyncChapterPipeline

Each pipeline package :
  types.py      — input props + stage-specific DTOs
  generator.py  — yields work items one at a time
  extract.py    — fetches raw data (browser, HTTP, and/or Firestore via store)
  transform.py  — pure mapping to load-ready documents (no I/O)
  load.py       — writes to Firestore/Storage (or skips on dry run)
  pipeline.py   — orchestrates the loop, stats, and error handling
```

Shared modules:

| Module | Role |
|--------|------|
| `store.py` | `MangaStore` abstraction (JSON files or Firestore) |
| `models.py` | Pydantic documents, storage path helpers, status enums |
| `types.py` | `PipelineOptions` shared by all pipelines |
| `config.py` | Environment-driven defaults |
| `chapter_selection.py` | Rules for picking pending chapters |
| `app/services/storage.py` | Firebase Storage uploads |

## The ETL pattern

Every pipeline follows the same loop:

```python
async for work_item in generator(...):
    raw = await extract(...)
    item = transform(raw, ...)
    await load(..., dry_run=props.dry_run)
```

### Generator

Yields **one work unit per iteration**, bounded by scope props on the input type (`limit`, `page_count`, etc.).

The generator decides *what* to process — either by reading from Firestore via the store (sync pipelines) or by driving an external sequence (e.g. listing pages). Props decide *how much*.

### Extract

Fetches raw input for transform. Sources include:

- **Browser** — scraped HTML / data URIs from the site
- **HTTP APIs** — e.g. chapter list endpoints
- **Firestore** (via `MangaStore`) — existing documents passed in from the generator, such as a pending manga stub or chapter subdoc to enrich

Extract returns a stage-specific result type defined in the pipeline's `types.py`. In sync pipelines, the generator reads work items from Firestore first; extract then combines that persisted state with freshly scraped data.

In some pipelines, extract is called inside the generator rather than as a separate step in the orchestrator. The responsibility is the same: produce raw input for transform.

### Transform

**Pure functions** — no Firestore, no Storage, no network. Map extract output into documents ready to load.

Keeping I/O out of transform makes it easy to test and reason about document shape independently of persistence.

### Load

Handles all side effects: Storage uploads, Firestore upserts, and failure state updates.

On **dry run**, load skips writes and logs `[Dry run] skipped loading ...`. See each pipeline doc for the exact message shape.

### Pipeline (orchestrator)

The `*Pipeline.run(props)` class ties the loop together:

- Opens one Chrome browser for the run
- Accumulates run stats returned as JSON
- Handles per-item errors without aborting the whole batch
- Applies delays between items (`props.delay_seconds`)

Pipeline-specific orchestration (e.g. marking items as in-progress before scrape) belongs here, not in transform or load.

## Input props

All pipelines extend `PipelineOptions`:

```python
class PipelineOptions(BaseModel):
    delay_seconds: float = 30.0
    dry_run: bool = False
    verbose: bool = False
```

Each pipeline adds its own scope props on top. See the individual pipeline docs for flags and defaults.

Props are the **only** limit on how much work a run does.

## CLI

```powershell
python cli.py pipeline discover ...
python cli.py pipeline sync ...
python cli.py pipeline sync-chapters ...
python cli.py pipeline status
```

Shared flags across sync pipelines:

| Flag | Effect |
|------|--------|
| `--dry-run` | Extract + transform run; load skips all writes |
| `--verbose` / `-v` | Log full scraped payloads after transform |
| `--delay` | Seconds between work items |

Each command prints a JSON stats object to stdout.

## Store layer

`MangaStore` is an abstract interface implemented by:

- **`JsonFileStore`** — local files under `data/pipeline/mangas/` (default, for development)
- **`FirestoreStore`** — production backend

Set `PIPELINE_STORE=firestore` to use Firestore. Chapter page uploads require Firestore + Storage.

The store exposes query and upsert methods that each pipeline's generator and load stages call. Individual pipeline docs note which methods they use.

## Dry run and verbose

**Dry run** runs extract and transform so you can inspect what *would* be written, without touching Firestore or Storage. All skip logging lives in each pipeline's `load.py`.

**Verbose** logs full payloads after transform, prefixed with `[Dry run]` when applicable.

## Run status

Each pipeline returns a `status` field derived from success/failure counts:

| Status | Meaning |
|--------|---------|
| `completed` | All items succeeded |
| `partially_completed` | Mix of success and failure |
| `failed` | All items failed, or the run crashed |

`pipeline status` reads live counts from the store:

```json
{
  "scrapeStatus": { "pending": 120, "synced": 45, "failed": 2 },
  "pendingChapters": 890,
  "mangaCount": 167
}
```

## Configuration

Environment variables (see `app/pipeline/config.py`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `PIPELINE_STORE` | `json` | `json` or `firestore` |
| `PIPELINE_STATE_DIR` | `data/pipeline` | Local JSON store directory |
| `PIPELINE_DELAY_SECONDS` | `30` | Default delay for sync pipelines |
| `PIPELINE_DISCOVER_DELAY_SECONDS` | `2` | Default delay between listing pages |
| `PIPELINE_MAX_RETRIES` | `3` | Manga sync failures before permanent `failed` |

Firebase credentials: `FIREBASE_PROJECT_ID`, credentials path, and optionally `FIREBASE_STORAGE_BUCKET`.

## Adding a new pipeline

1. Create `app/pipeline/my_pipeline/` with `types.py`, `generator.py`, `extract.py`, `transform.py`, `load.py`, `pipeline.py`
2. Define an input type extending `PipelineOptions` with scope props
3. Keep transform pure; put all I/O in extract and load
4. Register a method on `PipelineRunner` and a Typer command in `cli.py`
5. Add store methods if the pipeline needs new query patterns
6. Add a doc under `docs/topics/pipeline/`

The orchestrator (`pipeline.py`) should stay thin: loop, stats, delays, and error boundaries. Business logic belongs in the stage modules.

## File reference

```
app/pipeline/
  runner.py              CLI facade
  store.py               MangaStore (json | firestore)
  models.py              Documents, enums, path helpers
  types.py               PipelineOptions
  config.py              Env defaults
  chapter_selection.py   Pending chapter selection rules

  discover/              → see discover.md
  sync_manga/            → see sync-manga.md
  sync_chapter/          → see sync-chapters.md

app/services/
  storage.py             Firebase Storage uploads
```
