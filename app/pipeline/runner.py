import logging

from app.pipeline.config import (
    PIPELINE_DAILY_LIMIT,
    PIPELINE_DELAY_SECONDS,
    PIPELINE_DISCOVER_DELAY_SECONDS,
    PIPELINE_MAX_RETRIES,
)
from app.pipeline.models import JobStatus, JobType, QueueStatus, resolve_job_status, utcnow
from app.pipeline.state import PipelineState
from app.pipeline.steps import build_chapter_documents, discover_mangas_from_pages, sync_mangas_from_slugs
from app.pipeline.store import MangaStore, get_manga_store

logger = logging.getLogger(__name__)


class PipelineRunner:
    def __init__(
        self,
        state: PipelineState | None = None,
        store: MangaStore | None = None,
        daily_limit: int = PIPELINE_DAILY_LIMIT,
        delay_seconds: float = PIPELINE_DELAY_SECONDS,
    ) -> None:
        self.state = state or PipelineState()
        self.store = store or get_manga_store()
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
                    enqueued = self.state.enqueue_slugs(page_result.slugs)
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
        pending = self.state.get_pending_slugs(batch_size)

        job = self.state.start_job(
            JobType.SYNC_MANGA,
            {'limit': batch_size, 'dailyLimit': self.daily_limit},
        )
        stats: dict = {'processed': 0, 'failed': 0, 'skipped': 0, 'failedSlugs': []}
        slug_to_item = {item.slug: item for item in pending}

        for item in pending:
            item.status = QueueStatus.PROCESSING
            item.last_attempt_at = utcnow()
            self.state.update_queue_item(item)

        try:
            sync_result = await sync_mangas_from_slugs(
                [item.slug for item in pending],
                delay_seconds=self.delay_seconds,
            )

            for result in sync_result.results:
                item = slug_to_item[result.slug]

                if result.success and result.manga:
                    await self.store.upsert_manga(result.manga)
                    for chapter in build_chapter_documents(result.manga.chapter_numbers):
                        await self.store.upsert_chapter(result.slug, chapter)

                    item.status = QueueStatus.COMPLETED
                    item.last_error = None
                    stats['processed'] += 1
                    self.state.increment_daily_processed()
                else:
                    item.attempts += 1
                    item.last_error = result.error
                    item.status = (
                        QueueStatus.FAILED
                        if item.attempts >= PIPELINE_MAX_RETRIES
                        else QueueStatus.PENDING
                    )
                    stats['failed'] += 1
                    stats['failedSlugs'].append({
                        'slug': result.slug,
                        'error': result.error,
                    })

                self.state.update_queue_item(item)
        except Exception:
            for item in pending:
                if item.status == QueueStatus.PROCESSING:
                    item.status = QueueStatus.PENDING
                    self.state.update_queue_item(item)
            raise

        job_status = resolve_job_status(stats['processed'], stats['failed'])
        stats['status'] = job_status.value
        self.state.update_job(job, job_status, stats)
        return stats

    def status(self) -> dict:
        return self.state.get_status_summary()
