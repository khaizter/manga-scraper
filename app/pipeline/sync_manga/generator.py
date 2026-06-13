from collections.abc import AsyncIterator

from app.pipeline.models import MangaDocument
from app.pipeline.store import MangaStore
from app.pipeline.sync_manga.types import SyncMangaInput


async def generator(store: MangaStore, props: SyncMangaInput) -> AsyncIterator[MangaDocument]:
    """Yield one pending manga at a time (bounded by limit)."""
    pending = await store.get_pending_mangas(props.limit)

    for manga in pending:
        yield manga
