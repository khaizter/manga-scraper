from app.pipeline.discover.types import DiscoverLoadBatch, PageExtractResult


def transform_page(result: PageExtractResult) -> DiscoverLoadBatch:
    """Map a scraped listing page into a load batch."""
    return DiscoverLoadBatch(
        page=result.page,
        slugs=result.slugs,
        success=result.success,
        error=result.error,
    )
