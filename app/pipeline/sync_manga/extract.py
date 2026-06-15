import asyncio

from pydoll.browser.tab import Tab

from app.pipeline.sync_manga.types import MangaExtractResult
from app.services.chapters_api import fetch_chapter_numbers
from app.services.scrape_manga_details import scrape_manga_detail_on_tab


async def extract_manga(tab: Tab, slug: str) -> MangaExtractResult:
    """Fetch metadata and chapter list for a single manga."""
    detail, chapters = await asyncio.gather(
        scrape_manga_detail_on_tab(tab, slug),
        fetch_chapter_numbers(slug),
    )
    return MangaExtractResult(slug=slug, detail=detail, chapters=chapters)
