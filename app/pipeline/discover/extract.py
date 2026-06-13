from pydoll.browser.tab import Tab

from app.core.config import LIST_URL
from app.core.browser import navigate_to
from app.pipeline.discover.types import PageExtractResult
from app.services.manga_list import scrape_list_page_slugs


async def extract_listing_page(tab: Tab, page: int) -> PageExtractResult:
    """Fetch slugs from a single genre listing page."""
    try:
        await navigate_to(tab, f'{LIST_URL}?page={page}')
        slugs = await scrape_list_page_slugs(tab)
        if not slugs:
            raise ValueError('No manga slugs found on page')

        return PageExtractResult(page=page, slugs=slugs, success=True)
    except Exception as exc:
        return PageExtractResult(page=page, success=False, error=str(exc))
