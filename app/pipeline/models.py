"""
Firestore data model (recommended layout)
=========================================

Collections:

  mangas/{slug}
    slug: str
    title: str
    description: str | null
    author: str
    status: str                    # e.g. "Ongoing", "Completed"
    sourceUrl: str
    chapterCount: int
    coverStoragePath: str | null   # Firebase Storage path, NOT base64
    scrapeStatus: str              # pending | synced | failed
    lastSyncedAt: timestamp
    createdAt: timestamp
    updatedAt: timestamp

  mangas/{slug}/chapters/{chapterNumber}
    chapterNumber: str             # e.g. "336-1" (doc id)
    chapterSlug: str               # e.g. "chapter-336-1" (for scraping)
    pageCount: int
    scrapeStatus: str              # pending | synced | failed
    lastSyncedAt: timestamp | null

  mangas/{slug}/chapters/{chapterNumber}/pages/{pageIndex}
    pageIndex: int                 # 0-based doc id
    storagePath: str               # Firebase Storage path to image
    sourceUrl: str | null          # original CDN url (optional)
    lastSyncedAt: timestamp

  pipeline_jobs/{jobId}
    type: str                      # discover | sync_manga | sync_chapter
    status: str                    # running | completed | failed
    startedAt: timestamp
    completedAt: timestamp | null
    config: map
    stats: map                     # processed, failed, skipped

  pipeline_queue/{slug}
    slug: str                      # doc id
    status: str                    # pending | processing | completed | failed
    priority: int                  # lower = sooner
    discoveredAt: timestamp
    attempts: int
    lastAttemptAt: timestamp | null
    lastError: str | null

Notes:
  - Never store imageDataUri or page base64 in Firestore (1MB doc limit).
  - Upload images to Firebase Storage; store paths/URLs only.
  - Use pipeline_queue for scheduled Cloud Function work distribution.
  - Cloud Function can read queue, process N items, update docs, respect daily caps.
"""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ScrapeStatus(StrEnum):
    PENDING = 'pending'
    SYNCED = 'synced'
    FAILED = 'failed'


class QueueStatus(StrEnum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'


class JobType(StrEnum):
    DISCOVER = 'discover'
    SYNC_MANGA = 'sync_manga'
    SYNC_CHAPTER = 'sync_chapter'


class JobStatus(StrEnum):
    RUNNING = 'running'
    COMPLETED = 'completed'
    PARTIALLY_COMPLETED = 'partially_completed'
    FAILED = 'failed'


def resolve_job_status(succeeded: int, failed: int) -> JobStatus:
    if failed and succeeded:
        return JobStatus.PARTIALLY_COMPLETED
    if failed:
        return JobStatus.FAILED
    return JobStatus.COMPLETED


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class QueueItem(BaseModel):
    slug: str
    status: QueueStatus = QueueStatus.PENDING
    priority: int = 0
    discovered_at: datetime = Field(default_factory=utcnow)
    attempts: int = 0
    last_attempt_at: datetime | None = None
    last_error: str | None = None


class MangaDocument(BaseModel):
    slug: str
    title: str
    description: str | None = None
    author: str
    status: str
    source_url: str
    chapter_numbers: list[str] = Field(default_factory=list)
    chapter_count: int = 0
    cover_storage_path: str | None = None
    scrape_status: ScrapeStatus = ScrapeStatus.SYNCED
    last_synced_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @classmethod
    def from_scrape(cls, slug: str, data: dict[str, Any], source_url: str) -> 'MangaDocument':
        chapters = data.get('chapters', [])
        return cls(
            slug=slug,
            title=data['title'],
            description=data.get('description') or None,
            author=data['author'],
            status=data['status'],
            source_url=source_url,
            chapter_numbers=chapters,
            chapter_count=len(chapters),
        )


class ChapterDocument(BaseModel):
    chapter_number: str
    chapter_slug: str
    page_count: int = 0
    scrape_status: ScrapeStatus = ScrapeStatus.PENDING
    last_synced_at: datetime | None = None


class PageDiscoverResult(BaseModel):
    page: int
    slugs: list[str] = Field(default_factory=list)
    success: bool
    error: str | None = None


class DiscoverResult(BaseModel):
    page_results: list[PageDiscoverResult] = Field(default_factory=list)

    @property
    def all_slugs(self) -> list[str]:
        slugs: list[str] = []
        for result in self.page_results:
            slugs.extend(result.slugs)
        return slugs

    @property
    def succeeded_pages(self) -> list[int]:
        return [result.page for result in self.page_results if result.success]

    @property
    def failed_pages(self) -> list[PageDiscoverResult]:
        return [result for result in self.page_results if not result.success]


class SyncMangaResult(BaseModel):
    slug: str
    manga: MangaDocument | None = None
    success: bool
    error: str | None = None


class SyncMangasResult(BaseModel):
    results: list[SyncMangaResult] = Field(default_factory=list)

    @property
    def succeeded(self) -> list[SyncMangaResult]:
        return [result for result in self.results if result.success]

    @property
    def failed(self) -> list[SyncMangaResult]:
        return [result for result in self.results if not result.success]


class PipelineJob(BaseModel):
    id: str
    type: JobType
    status: JobStatus = JobStatus.RUNNING
    started_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    stats: dict[str, Any] = Field(default_factory=dict)
