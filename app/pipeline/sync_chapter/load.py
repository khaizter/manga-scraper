import logging

from app.pipeline.models import ChapterDocument, ScrapeStatus
from app.pipeline.store import MangaStore
from app.pipeline.sync_chapter.types import SyncChapterLoadItem
from app.services.storage import upload_chapter_pages

logger = logging.getLogger(__name__)


async def load_success(store: MangaStore, item: SyncChapterLoadItem, *, dry_run: bool) -> None:
    """Upload page images and persist the chapter document."""
    if dry_run:
        logger.info(
            '[Dry run] skipped loading chapter %s/%s (%d page(s))',
            item.manga_slug,
            item.chapter.chapter_number,
            len(item.pages),
        )
        return

    await upload_chapter_pages(
        item.manga_slug,
        item.chapter.chapter_number,
        item.pages,
    )
    await store.upsert_chapter(item.manga_slug, item.chapter)


async def load_failure(
    store: MangaStore,
    manga_slug: str,
    chapter: ChapterDocument,
    *,
    dry_run: bool,
) -> None:
    """Record a failed chapter sync attempt."""
    if dry_run:
        logger.info(
            '[Dry run] skipped loading failure state for chapter %s/%s',
            manga_slug,
            chapter.chapter_number,
        )
        return

    chapter.scrape_status = ScrapeStatus.FAILED
    await store.upsert_chapter(manga_slug, chapter)
