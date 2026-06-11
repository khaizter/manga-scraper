import asyncio
import logging

from pydoll.browser.chromium import Chrome

from app.core.browser import get_chrome_options, start_tab
from app.pipeline.config import (
    PIPELINE_DAILY_LIMIT,
    PIPELINE_DELAY_SECONDS,
    PIPELINE_DISCOVER_DELAY_SECONDS,
    PIPELINE_MAX_RETRIES,
)
from app.pipeline.models import JobStatus, JobType, ScrapeStatus, resolve_job_status, utcnow
from app.pipeline.state import PipelineState
from app.pipeline.steps import build_chapter_documents, discover_mangas_from_pages
from app.pipeline.store import MangaStore, get_manga_store
from app.services.manga import sync_manga_on_tab
from app.services.manga_chapter import sync_chapter_on_tab

logger = logging.getLogger(__name__)


class PipelineRunner:
    def __init__(
        self,
        state: PipelineState | None = None,
        store: MangaStore | None = None,
        daily_limit: int = PIPELINE_DAILY_LIMIT,
        delay_seconds: float = PIPELINE_DELAY_SECONDS,
    ) -> None:
        self.store = store or get_manga_store()
        self.state = state or PipelineState(manga_store=self.store)
        self.daily_limit = daily_limit
        self.delay_seconds = delay_seconds

    async def discover(
        self,
        start_page: int = 1,
        page_count: int = 1,
        *,
        delay_seconds: float = PIPELINE_DISCOVER_DELAY_SECONDS,
    ) -> dict:
        if page_count < 1:
            raise ValueError(f'page_count ({page_count}) must be >= 1')

        end_page = start_page + page_count - 1

        job = self.state.start_job(
            JobType.DISCOVER,
            {
                'startPage': start_page,
                'pageCount': page_count,
                'endPage': end_page,
                'delaySeconds': delay_seconds,
            },
        )
        stats: dict = {
            'startPage': start_page,
            'pageCount': page_count,
            'endPage': end_page,
            'discovered': 0,
            'enqueued': 0,
            'pagesSucceeded': 0,
            'pagesFailed': 0,
            'failedPages': [],
        }

        try:
            result = await discover_mangas_from_pages(
                start_page,
                end_page,
                delay_seconds=delay_seconds,
            )

            for page_result in result.page_results:
                if page_result.success:
                    enqueued = await self.store.enqueue_slugs(page_result.slugs)
                    stats['discovered'] += len(page_result.slugs)
                    stats['enqueued'] += enqueued
                    stats['pagesSucceeded'] += 1
                else:
                    stats['pagesFailed'] += 1
                    stats['failedPages'].append({
                        'page': page_result.page,
                        'error': page_result.error,
                    })

            job_status = resolve_job_status(
                stats['pagesSucceeded'],
                stats['pagesFailed'],
            )
            stats['status'] = job_status.value
            self.state.update_job(job, job_status, stats)
            return stats
        except Exception:
            stats['failed'] = 1
            self.state.update_job(job, JobStatus.FAILED, stats)
            raise

    async def _reset_stuck_processing(self, slugs: list[str]) -> None:
        for slug in slugs:
            manga = await self.store.get_manga(slug)
            if manga and manga.scrape_status == ScrapeStatus.PROCESSING:
                manga.scrape_status = ScrapeStatus.PENDING
                await self.store.upsert_manga(manga)

    async def sync_mangas(self, limit: int | None = None) -> dict:
        remaining_today = max(0, self.daily_limit - self.state.get_daily_processed_count())
        if remaining_today == 0:
            return {
                'processed': 0,
                'failed': 0,
                'skipped': 0,
                'message': f'Daily limit of {self.daily_limit} reached',
            }

        batch_size = min(limit or remaining_today, remaining_today)
        pending = await self.store.get_pending_mangas(batch_size)

        if not pending:
            return {'processed': 0, 'failed': 0, 'skipped': 0, 'message': 'No pending mangas'}

        batch_slugs = [manga.slug for manga in pending]

        job = self.state.start_job(
            JobType.SYNC_MANGA,
            {'limit': batch_size, 'dailyLimit': self.daily_limit},
        )
        stats: dict = {'processed': 0, 'failed': 0, 'skipped': 0, 'failedSlugs': []}

        try:
            options = get_chrome_options()
            async with Chrome(options=options) as browser:
                tab = await start_tab(browser)
                for index, existing in enumerate(pending):
                    existing.scrape_status = ScrapeStatus.PROCESSING
                    existing.last_attempt_at = utcnow()
                    await self.store.upsert_manga(existing)

                    try:
                        scraped = await sync_manga_on_tab(tab, existing.slug)
                        manga = scraped
                        manga.created_at = existing.created_at
                        manga.discovered_at = existing.discovered_at
                        manga.attempts = 0
                        manga.last_error = None
                        await self.store.upsert_manga(manga)
                        for chapter in build_chapter_documents(manga.chapters):
                            await self.store.upsert_chapter(existing.slug, chapter)

                        stats['processed'] += 1
                        self.state.increment_daily_processed()
                        logger.info('Synced manga: %s (%d chapters)', existing.slug, len(manga.chapters))
                    except Exception as exc:
                        error = str(exc)
                        existing.attempts += 1
                        existing.last_error = error
                        existing.scrape_status = (
                            ScrapeStatus.FAILED
                            if existing.attempts >= PIPELINE_MAX_RETRIES
                            else ScrapeStatus.PENDING
                        )
                        await self.store.upsert_manga(existing)
                        stats['failed'] += 1
                        stats['failedSlugs'].append({
                            'slug': existing.slug,
                            'error': error,
                        })
                        logger.error('Failed to sync manga %s: %s', existing.slug, error, exc_info=True)

                    if index < len(pending) - 1:
                        await asyncio.sleep(self.delay_seconds)
        except Exception:
            await self._reset_stuck_processing(batch_slugs)
            stats['status'] = JobStatus.FAILED.value
            self.state.update_job(job, JobStatus.FAILED, stats)
            raise

        job_status = resolve_job_status(stats['processed'], stats['failed'])
        stats['status'] = job_status.value
        self.state.update_job(job, job_status, stats)
        return stats

    async def sync_chapters(self, limit: int | None = None) -> dict:
        remaining_today = max(0, self.daily_limit - self.state.get_daily_processed_count())
        if remaining_today == 0:
            return {
                'processed': 0,
                'failed': 0,
                'skipped': 0,
                'message': f'Daily limit of {self.daily_limit} reached',
            }

        batch_size = min(limit or remaining_today, remaining_today)
        pending = await self.store.get_pending_chapters(batch_size)

        if not pending:
            return {
                'processed': 0,
                'failed': 0,
                'skipped': 0,
                'message': 'No pending chapters',
            }

        job = self.state.start_job(
            JobType.SYNC_CHAPTER,
            {'limit': batch_size, 'dailyLimit': self.daily_limit},
        )
        stats: dict = {'processed': 0, 'failed': 0, 'skipped': 0, 'failedChapters': []}

        try:
            options = get_chrome_options()
            async with Chrome(options=options) as browser:
                tab = await start_tab(browser)
                for index, item in enumerate(pending):
                    try:
                        synced_chapter = await sync_chapter_on_tab(
                            tab,
                            item.manga_slug,
                            item.chapter,
                        )
                        await self.store.upsert_chapter(item.manga_slug, synced_chapter)
                        stats['processed'] += 1
                        self.state.increment_daily_processed()
                        logger.info(
                            'Synced chapter: %s/%s (%d pages)',
                            item.manga_slug,
                            item.chapter.chapter_number,
                            len(synced_chapter.storage_paths),
                        )
                    except Exception as exc:
                        error = str(exc)
                        failed_chapter = item.chapter
                        failed_chapter.scrape_status = ScrapeStatus.FAILED
                        await self.store.upsert_chapter(item.manga_slug, failed_chapter)
                        stats['failed'] += 1
                        stats['failedChapters'].append({
                            'mangaSlug': item.manga_slug,
                            'chapterNumber': item.chapter.chapter_number,
                            'error': error,
                        })
                        logger.error(
                            'Failed to sync chapter %s/%s: %s',
                            item.manga_slug,
                            item.chapter.chapter_number,
                            error,
                            exc_info=True,
                        )

                    if index < len(pending) - 1:
                        await asyncio.sleep(self.delay_seconds)
        except Exception:
            stats['status'] = JobStatus.FAILED.value
            self.state.update_job(job, JobStatus.FAILED, stats)
            raise

        job_status = resolve_job_status(stats['processed'], stats['failed'])
        stats['status'] = job_status.value
        self.state.update_job(job, job_status, stats)
        return stats

    async def status(self) -> dict:
        return await self.state.get_status_summary()
