import logging

from app.pipeline.config import PIPELINE_MAX_RETRIES, PIPELINE_STORE
from app.pipeline.models import MangaDocument, ScrapeStatus
from app.pipeline.store import MangaStore
from app.pipeline.sync_manga.types import SyncMangaLoadItem
from app.services.storage import upload_manga_cover

logger = logging.getLogger(__name__)


async def load_success(store: MangaStore, item: SyncMangaLoadItem, *, dry_run: bool) -> None:
    """Upload cover and persist manga + chapter stubs."""
    if dry_run:
        logger.info(
            '[Dry run] skipped loading manga %s (%d chapter stub(s))',
            item.manga.slug,
            len(item.chapters),
        )
        return

    if item.cover_data_uri and PIPELINE_STORE == 'firestore':
        try:
            item.manga.cover_storage_path = await upload_manga_cover(
                item.manga.slug,
                item.cover_data_uri,
            )
        except Exception as exc:
            logger.warning('Failed to upload cover for %s: %s', item.manga.slug, exc)

    await store.upsert_manga(item.manga)
    for chapter in item.chapters:
        await store.upsert_chapter(item.manga.slug, chapter)


async def load_failure(
    store: MangaStore,
    existing: MangaDocument,
    error: str,
    *,
    dry_run: bool,
) -> None:
    """Record a failed manga sync attempt."""
    if dry_run:
        logger.info('[Dry run] skipped loading failure state for manga %s', existing.slug)
        return

    existing.attempts += 1
    existing.last_error = error
    existing.scrape_status = (
        ScrapeStatus.FAILED
        if existing.attempts >= PIPELINE_MAX_RETRIES
        else ScrapeStatus.PENDING
    )
    await store.upsert_manga(existing)
