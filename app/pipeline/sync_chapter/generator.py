from collections.abc import AsyncIterator

from app.pipeline.models import PendingChapter
from app.pipeline.store import MangaStore
from app.pipeline.sync_chapter.types import SyncChapterInput


async def generator(store: MangaStore, props: SyncChapterInput) -> AsyncIterator[PendingChapter]:
    """Yield one pending chapter at a time (bounded by limit)."""
    pending = await store.get_pending_chapters(props.limit)

    for item in pending:
        yield item
