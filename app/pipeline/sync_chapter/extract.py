from pydoll.browser.tab import Tab

from app.pipeline.models import ChapterDocument
from app.pipeline.sync_chapter.types import ChapterExtractResult
from app.services.manga_chapter import scrape_chapter_pages_on_tab


async def extract_chapter(
    tab: Tab,
    manga_slug: str,
    chapter: ChapterDocument,
) -> ChapterExtractResult:
    """Fetch page image data URIs for a single chapter."""
    page_data_uris = await scrape_chapter_pages_on_tab(tab, manga_slug, chapter.chapter_slug)
    return ChapterExtractResult(
        manga_slug=manga_slug,
        chapter=chapter,
        page_data_uris=page_data_uris,
    )
