import asyncio
import logging

from pydoll.browser.chromium import Chrome

from app.core.browser import get_chrome_options, start_tab
from app.pipeline.models import JobStatus, ScrapeStatus, resolve_job_status, utcnow
from app.pipeline.store import MangaStore
from app.pipeline.sync_manga.extract import extract_manga
from app.pipeline.sync_manga.generator import generator
from app.pipeline.sync_manga.load import load_failure, load_success
from app.pipeline.sync_manga.transform import transform_manga
from app.pipeline.sync_manga.types import SyncMangaInput

logger = logging.getLogger(__name__)


class SyncMangaPipeline:
    def __init__(self, store: MangaStore) -> None:
        self.store = store

    async def _reset_stuck_processing(self, slugs: list[str]) -> None:
        for slug in slugs:
            manga = await self.store.get_manga(slug)
            if manga and manga.scrape_status == ScrapeStatus.PROCESSING:
                manga.scrape_status = ScrapeStatus.PENDING
                await self.store.upsert_manga(manga)

    async def run(self, props: SyncMangaInput) -> dict:
        stats: dict = {'processed': 0, 'failed': 0, 'skipped': 0, 'failedSlugs': []}
        batch_slugs: list[str] = []
        processed_any = False

        try:
            options = get_chrome_options()
            async with Chrome(options=options) as browser:
                tab = await start_tab(browser)
                index = 0

                async for existing in generator(self.store, props):
                    processed_any = True
                    batch_slugs.append(existing.slug)

                    if not props.dry_run:
                        existing.scrape_status = ScrapeStatus.PROCESSING
                        existing.last_attempt_at = utcnow()
                        await self.store.upsert_manga(existing)

                    try:
                        raw = await extract_manga(tab, existing.slug)
                        item = transform_manga(raw, existing)
                        await load_success(self.store, item, dry_run=props.dry_run)

                        stats['processed'] += 1

                        if props.verbose:
                            logger.info(
                                '%sFound manga %s (%d chapters): %s, chapter slugs: %s',
                                '[Dry run] ' if props.dry_run else '',
                                existing.slug,
                                len(item.manga.chapters),
                                item.manga.model_dump(mode='json', by_alias=True),
                                [chapter.chapter_slug for chapter in item.chapters],
                            )
                        elif not props.dry_run:
                            logger.info(
                                'Synced manga: %s (%d chapters)',
                                existing.slug,
                                len(item.manga.chapters),
                            )
                    except Exception as exc:
                        error = str(exc)
                        await load_failure(self.store, existing, error, dry_run=props.dry_run)
                        stats['failed'] += 1
                        stats['failedSlugs'].append({'slug': existing.slug, 'error': error})
                        logger.error('Failed to sync manga %s: %s', existing.slug, error, exc_info=True)

                    if index < props.limit - 1:
                        await asyncio.sleep(props.delay_seconds)
                    index += 1

        except Exception:
            if not props.dry_run:
                await self._reset_stuck_processing(batch_slugs)
            stats['status'] = JobStatus.FAILED.value
            raise

        if not processed_any:
            return {'processed': 0, 'failed': 0, 'skipped': 0, 'message': 'No pending mangas'}

        stats['status'] = resolve_job_status(stats['processed'], stats['failed']).value
        return stats
