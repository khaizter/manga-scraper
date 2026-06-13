"""
Firestore data model (recommended layout)
=========================================

Collections:

  mangas/{slug}
    slug: str
    title: str | null              # null until first sync
    description: str | null
    author: str | null
    status: str | null             # e.g. "Ongoing", "Completed"
    sourceUrl: str | null
    chapters: str[]                # chapter count = len(chapters)
    coverStoragePath: str | null   # Firebase Storage path, NOT base64
    scrapeStatus: str              # pending | processing | synced | failed
    discoveredAt: timestamp
    attempts: int
    lastAttemptAt: timestamp | null
    lastError: str | null
    lastSyncedAt: timestamp | null
    createdAt: timestamp
    updatedAt: timestamp

  mangas/{slug}/chapters/{chapterNumber}
    chapterNumber: str             # e.g. "336-1" (doc id)
    chapterSlug: str               # e.g. "chapter-336-1" (for scraping)
    storagePaths: str[]            # ordered Firebase Storage paths; page count = len(storagePaths)
    scrapeStatus: str              # pending | synced | failed
    lastSyncedAt: timestamp | null

Firebase Storage layout (default bucket: {projectId}.firebasestorage.app)
=========================================================================

All paths are lowercase, kebab-case slugs, relative to the bucket root.
Firestore stores the path string only — never image bytes or data URIs.

  mangas/{slug}/cover.{ext}
    Manga cover image (sync_manga).
    Referenced by mangas/{slug}.coverStoragePath.
    ext: jpg | png | webp | gif (from source mime type).

  mangas/{slug}/chapters/{chapterNumber}/{pageIndex}.{ext}
    Chapter page images (sync_chapter), 0-based pageIndex.
    Ordered paths collected into chapters/{chapterNumber}.storagePaths.
    Example:
      mangas/black-clover/chapters/336-1/0.webp
      mangas/black-clover/chapters/336-1/1.webp

Notes:
  - Never store imageDataUri or page base64 in Firestore (1MB doc limit).
  - Upload images to Firebase Storage; store paths/URLs only.
  - Discover creates pending manga stubs; sync enriches the same document.
  - Filter scrapeStatus != synced in app-facing reads.

Chapter pipeline selection (sync_chapter)
=======================================
  1. Manga scrapeStatus == synced
  2. For each chapterNumber in manga.chapters (in order):
       - chapters/{chapterNumber} missing → treat as pending stub
       - chapters/{chapterNumber}.scrapeStatus != synced → eligible
  3. Oldest manga.discoveredAt first; within a manga, follow chapters[] order
"""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ScrapeStatus(StrEnum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    SYNCED = 'synced'
    FAILED = 'failed'


class JobStatus(StrEnum):
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


STORAGE_MANGAS_PREFIX = 'mangas'


def manga_cover_storage_path(slug: str, extension: str) -> str:
    """Storage path for a manga cover (sync_manga)."""
    return f'{STORAGE_MANGAS_PREFIX}/{slug}/cover.{extension}'


def chapter_page_storage_path(
    slug: str,
    chapter_number: str,
    page_index: int,
    extension: str,
) -> str:
    """Storage path for a single chapter page (sync_chapter). page_index is 0-based."""
    return (
        f'{STORAGE_MANGAS_PREFIX}/{slug}/chapters/{chapter_number}/{page_index}.{extension}'
    )


class MangaDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    slug: str
    title: str | None = None
    description: str | None = None
    author: str | None = None
    status: str | None = None
    source_url: str | None = Field(
        default=None,
        alias='sourceUrl',
        validation_alias=AliasChoices('sourceUrl', 'source_url'),
    )
    chapters: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices('chapters', 'chapterNumbers', 'chapter_numbers'),
    )
    cover_storage_path: str | None = Field(
        default=None,
        alias='coverStoragePath',
        validation_alias=AliasChoices('coverStoragePath', 'cover_storage_path'),
    )
    scrape_status: ScrapeStatus = Field(
        default=ScrapeStatus.PENDING,
        alias='scrapeStatus',
        validation_alias=AliasChoices('scrapeStatus', 'scrape_status'),
    )
    discovered_at: datetime = Field(
        default_factory=utcnow,
        alias='discoveredAt',
        validation_alias=AliasChoices('discoveredAt', 'discovered_at'),
    )
    attempts: int = 0
    last_attempt_at: datetime | None = Field(
        default=None,
        alias='lastAttemptAt',
        validation_alias=AliasChoices('lastAttemptAt', 'last_attempt_at'),
    )
    last_error: str | None = Field(
        default=None,
        alias='lastError',
        validation_alias=AliasChoices('lastError', 'last_error'),
    )
    last_synced_at: datetime | None = Field(
        default=None,
        alias='lastSyncedAt',
        validation_alias=AliasChoices('lastSyncedAt', 'last_synced_at'),
    )
    created_at: datetime = Field(
        default_factory=utcnow,
        alias='createdAt',
        validation_alias=AliasChoices('createdAt', 'created_at'),
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        alias='updatedAt',
        validation_alias=AliasChoices('updatedAt', 'updated_at'),
    )

    @classmethod
    def pending_stub(cls, slug: str) -> 'MangaDocument':
        now = utcnow()
        return cls(
            slug=slug,
            scrape_status=ScrapeStatus.PENDING,
            discovered_at=now,
            created_at=now,
            attempts=0,
            last_error=None,
            updated_at=now,
        )

    @classmethod
    def from_scrape(
        cls,
        slug: str,
        data: dict[str, Any],
        source_url: str,
        *,
        cover_storage_path: str | None = None,
    ) -> 'MangaDocument':
        chapters = data.get('chapters', [])
        now = utcnow()
        return cls(
            slug=slug,
            title=data['title'],
            description=data.get('description') or None,
            author=data['author'],
            status=data['status'],
            source_url=source_url,
            chapters=chapters,
            cover_storage_path=cover_storage_path,
            scrape_status=ScrapeStatus.SYNCED,
            last_synced_at=now,
            updated_at=now,
        )


class ChapterDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    chapter_number: str = Field(
        alias='chapterNumber',
        validation_alias=AliasChoices('chapterNumber', 'chapter_number'),
    )
    chapter_slug: str = Field(
        alias='chapterSlug',
        validation_alias=AliasChoices('chapterSlug', 'chapter_slug'),
    )
    storage_paths: list[str] = Field(
        default_factory=list,
        alias='storagePaths',
        validation_alias=AliasChoices('storagePaths', 'storage_paths'),
    )
    scrape_status: ScrapeStatus = Field(
        default=ScrapeStatus.PENDING,
        alias='scrapeStatus',
        validation_alias=AliasChoices('scrapeStatus', 'scrape_status'),
    )
    last_synced_at: datetime | None = Field(
        default=None,
        alias='lastSyncedAt',
        validation_alias=AliasChoices('lastSyncedAt', 'last_synced_at'),
    )


def chapter_needs_sync(chapter: ChapterDocument) -> bool:
    """True when chapter page images still need to be uploaded."""
    return chapter.scrape_status != ScrapeStatus.SYNCED


class PendingChapter(BaseModel):
    manga_slug: str
    chapter: ChapterDocument


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
