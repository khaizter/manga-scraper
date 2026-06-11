import asyncio
import logging
from typing import Any

from pydoll.browser.chromium import Chrome
from pydoll.browser.tab import Tab

from app.core.browser import get_chrome_options, navigate_to, start_tab
from app.core.config import BASE_URL, SCRAPE_TIMEOUT
from app.pipeline.config import PIPELINE_STORE
from app.pipeline.models import ChapterDocument, ScrapeStatus, utcnow
from app.services.chapters_api import fetch_chapter_numbers
from app.services.storage import upload_chapter_pages
from app.utils.image import fetch_image_data_uris_from_selector

logger = logging.getLogger(__name__)

CHAPTER_IMAGE_SELECTOR = 'div.container-chapter-reader > img'


async def scrape_chapter_pages_on_tab(
    tab: Tab,
    manga_slug: str,
    chapter_slug: str,
) -> list[str]:
    await navigate_to(tab, f'{BASE_URL}/manga/{manga_slug}/{chapter_slug}')
    return await fetch_image_data_uris_from_selector(
        tab,
        CHAPTER_IMAGE_SELECTOR,
        timeout=SCRAPE_TIMEOUT,
    )


async def scrape_chapter_pages(manga_slug: str, chapter_slug: str) -> list[str]:
    options = get_chrome_options()

    async with Chrome(options=options) as browser:
        tab = await start_tab(browser)
        return await scrape_chapter_pages_on_tab(tab, manga_slug, chapter_slug)


async def sync_chapter_on_tab(
    tab: Tab,
    manga_slug: str,
    chapter: ChapterDocument,
) -> ChapterDocument:
    page_uris = await scrape_chapter_pages_on_tab(tab, manga_slug, chapter.chapter_slug)
    if not page_uris:
        raise ValueError('No chapter pages found')

    if PIPELINE_STORE != 'firestore':
        raise ValueError('Chapter page upload requires PIPELINE_STORE=firestore')

    storage_paths = await upload_chapter_pages(
        manga_slug,
        chapter.chapter_number,
        page_uris,
    )

    return ChapterDocument(
        chapter_number=chapter.chapter_number,
        chapter_slug=chapter.chapter_slug,
        storage_paths=storage_paths,
        scrape_status=ScrapeStatus.SYNCED,
        last_synced_at=utcnow(),
    )


async def get_manga_chapter(manga_slug: str, chapter_slug: str) -> dict[str, Any]:
    pages, chapters = await asyncio.gather(
        scrape_chapter_pages(manga_slug, chapter_slug),
        fetch_chapter_numbers(manga_slug),
    )

    return {
        'mangaSlug': manga_slug,
        'chapterSlug': chapter_slug,
        'chapters': chapters,
        'pages': pages,
    }
