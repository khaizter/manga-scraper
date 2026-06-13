import logging

from app.pipeline.config import PIPELINE_DELAY_SECONDS, PIPELINE_DISCOVER_DELAY_SECONDS
from app.pipeline.discover.pipeline import DiscoverPipeline
from app.pipeline.discover.types import DiscoverInput
from app.pipeline.store import MangaStore, get_manga_store
from app.pipeline.sync_chapter.pipeline import SyncChapterPipeline
from app.pipeline.sync_chapter.types import SyncChapterInput
from app.pipeline.sync_manga.pipeline import SyncMangaPipeline
from app.pipeline.sync_manga.types import SyncMangaInput

logger = logging.getLogger(__name__)


class PipelineRunner:
    """Thin entry point that delegates to ETL pipeline modules."""

    def __init__(
        self,
        store: MangaStore | None = None,
        delay_seconds: float = PIPELINE_DELAY_SECONDS,
    ) -> None:
        self.store = store or get_manga_store()
        self.delay_seconds = delay_seconds

    async def discover(
        self,
        start_page: int = 1,
        page_count: int = 1,
        *,
        delay_seconds: float = PIPELINE_DISCOVER_DELAY_SECONDS,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> dict:
        pipeline = DiscoverPipeline(self.store)
        return await pipeline.run(
            DiscoverInput(
                start_page=start_page,
                page_count=page_count,
                delay_seconds=delay_seconds,
                dry_run=dry_run,
                verbose=verbose,
            ),
        )

    async def sync_mangas(
        self,
        limit: int = 10,
        *,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> dict:
        pipeline = SyncMangaPipeline(self.store)
        return await pipeline.run(
            SyncMangaInput(
                limit=limit,
                delay_seconds=self.delay_seconds,
                dry_run=dry_run,
                verbose=verbose,
            ),
        )

    async def sync_chapters(
        self,
        limit: int = 10,
        *,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> dict:
        pipeline = SyncChapterPipeline(self.store)
        return await pipeline.run(
            SyncChapterInput(
                limit=limit,
                delay_seconds=self.delay_seconds,
                dry_run=dry_run,
                verbose=verbose,
            ),
        )

    async def status(self) -> dict:
        counts = await self.store.count_scrape_status()
        pending_chapters = await self.store.count_pending_chapters()
        return {
            'scrapeStatus': counts,
            'pendingChapters': pending_chapters,
            'mangaCount': sum(counts.values()),
        }
