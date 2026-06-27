import asyncio
import logging

from pydoll.browser.chromium import Chrome

from app.core.browser import get_chrome_options, start_tab
from app.pipeline.discover.generator import generator
from app.pipeline.discover.load import load_batch
from app.pipeline.discover.transform import transform_page
from app.pipeline.discover.types import DiscoverInput
from app.pipeline.models import JobStatus, resolve_job_status
from app.pipeline.store import MangaStore

logger = logging.getLogger(__name__)


class DiscoverPipeline:
    def __init__(self, store: MangaStore) -> None:
        self.store = store

    async def run(self, props: DiscoverInput) -> dict:
        if props.page_count < 1:
            raise ValueError(f'page_count ({props.page_count}) must be >= 1')

        stats: dict = {
            'startPage': props.start_page,
            'pageCount': props.page_count,
            'endPage': props.end_page,
            'delaySeconds': props.delay_seconds,
            'dryRun': props.dry_run,
            'discovered': 0,
            'enqueued': 0,
            'pagesSucceeded': 0,
            'pagesFailed': 0,
            'failedPages': [],
        }

        try:
            options = get_chrome_options()
            async with Chrome(options=options) as browser:
                tab = await start_tab(browser)
                index = 0

                async for page_result in generator(tab, props):
                    batch = transform_page(page_result)

                    if batch.success:
                        enqueued = await load_batch(self.store, batch, dry_run=props.dry_run)
                        stats['discovered'] += len(batch.slugs)
                        stats['enqueued'] += enqueued
                        stats['pagesSucceeded'] += 1
                        if props.verbose:
                            logger.info(
                                '%sDiscover page %d: %d slug(s): %s, %d enqueued',
                                '[Dry run] ' if props.dry_run else '',
                                batch.page,
                                len(batch.slugs),
                                batch.slugs,
                                enqueued,
                            )
                    else:
                        stats['pagesFailed'] += 1
                        stats['failedPages'].append({
                            'page': batch.page,
                            'error': batch.error,
                        })
                        logger.error('Discover page %d failed: %s', batch.page, batch.error)

                    if index < props.page_count - 1:
                        await asyncio.sleep(props.delay_seconds)
                    index += 1
            stats['status'] = resolve_job_status(
                stats['pagesSucceeded'],
                stats['pagesFailed'],
            ).value
            return stats
        except Exception:
            stats['status'] = JobStatus.FAILED.value
            raise
