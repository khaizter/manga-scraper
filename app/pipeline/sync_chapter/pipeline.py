import asyncio
import logging

from pydoll.browser.chromium import Chrome

from app.core.browser import get_chrome_options, start_tab
from app.pipeline.models import JobStatus, resolve_job_status
from app.pipeline.store import MangaStore
from app.pipeline.sync_chapter.extract import extract_chapter
from app.pipeline.sync_chapter.generator import generator
from app.pipeline.sync_chapter.load import load_failure, load_success
from app.pipeline.sync_chapter.transform import transform_chapter
from app.pipeline.sync_chapter.types import SyncChapterInput

logger = logging.getLogger(__name__)


class SyncChapterPipeline:
    def __init__(self, store: MangaStore) -> None:
        self.store = store

    async def run(self, props: SyncChapterInput) -> dict:
        stats: dict = {
            'limit': props.limit,
            'delaySeconds': props.delay_seconds,
            'dryRun': props.dry_run,
            'processed': 0,
            'failed': 0,
            'skipped': 0,
            'failedChapters': [],
        }
        processed_any = False

        try:
            options = get_chrome_options()
            async with Chrome(options=options) as browser:
                tab = await start_tab(browser)
                index = 0

                async for pending in generator(self.store, props):
                    processed_any = True

                    try:
                        raw = await extract_chapter(tab, pending.manga_slug, pending.chapter)
                        item = transform_chapter(raw)
                        await load_success(self.store, item, dry_run=props.dry_run)

                        stats['processed'] += 1

                        if props.verbose:
                            logger.info(
                                '%sFoud chapter %s/%s (%d pages): %s, storage paths: %s',
                                '[Dry run] ' if props.dry_run else '',
                                pending.manga_slug,
                                pending.chapter.chapter_number,
                                len(item.pages),
                                item.chapter.model_dump(mode='json', by_alias=True),
                                item.chapter.storage_paths,
                            )
                        elif not props.dry_run:
                            logger.info(
                                'Synced chapter: %s/%s (%d pages)',
                                pending.manga_slug,
                                pending.chapter.chapter_number,
                                len(item.pages),
                            )
                    except Exception as exc:
                        error = str(exc)
                        await load_failure(
                            self.store,
                            pending.manga_slug,
                            pending.chapter,
                            dry_run=props.dry_run,
                        )
                        stats['failed'] += 1
                        stats['failedChapters'].append({
                            'mangaSlug': pending.manga_slug,
                            'chapterNumber': pending.chapter.chapter_number,
                            'error': error,
                        })
                        logger.error(
                            'Failed to sync chapter %s/%s: %s',
                            pending.manga_slug,
                            pending.chapter.chapter_number,
                            error,
                            exc_info=True,
                        )

                    if index < props.limit - 1:
                        await asyncio.sleep(props.delay_seconds)
                    index += 1

        except Exception:
            stats['status'] = JobStatus.FAILED.value
            raise

        if not processed_any:
            return {
                'limit': props.limit,
                'delaySeconds': props.delay_seconds,
                'dryRun': props.dry_run,
                'processed': 0,
                'failed': 0,
                'skipped': 0,
                'message': 'No pending chapters',
            }

        stats['status'] = resolve_job_status(stats['processed'], stats['failed']).value
        return stats
