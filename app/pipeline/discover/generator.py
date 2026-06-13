import asyncio
from collections.abc import AsyncIterator

from pydoll.browser.tab import Tab

from app.pipeline.discover.extract import extract_listing_page
from app.pipeline.discover.types import DiscoverInput, PageExtractResult


async def generator(tab: Tab, props: DiscoverInput) -> AsyncIterator[PageExtractResult]:
    """Yield one listing page batch at a time."""
    for page in range(props.start_page, props.end_page + 1):
        yield await extract_listing_page(tab, page)

        if page < props.end_page:
            await asyncio.sleep(props.delay_seconds)
