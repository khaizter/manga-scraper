import logging

from app.pipeline.discover.types import DiscoverLoadBatch
from app.pipeline.store import MangaStore

logger = logging.getLogger(__name__)


async def load_batch(store: MangaStore, batch: DiscoverLoadBatch, *, dry_run: bool) -> int:
    """Persist discovered slugs as pending manga stubs."""
    if dry_run:
        if batch.slugs:
            logger.info('[Dry run] skipped loading %d slug(s)', len(batch.slugs))
        return 0

    if not batch.success or not batch.slugs:
        return 0

    return await store.enqueue_slugs(batch.slugs)
