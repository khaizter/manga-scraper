import asyncio
from typing import Any

from pydoll.browser.chromium import Chrome
from pydoll.browser.tab import Tab

from app.core.browser import get_chrome_options, navigate_to, start_tab
from app.core.config import BASE_URL, SCRAPE_TIMEOUT
from app.services.chapters_api import fetch_chapter_numbers
from app.utils.image import fetch_image_data_uri_from_element

CHAPTER_IMAGE_SELECTOR = 'div.container-chapter-reader > img'


async def scrape_chapter_pages_on_tab(
    tab: Tab,
    manga_slug: str,
    chapter_slug: str,
) -> list[str]:
    await navigate_to(tab, f'{BASE_URL}/manga/{manga_slug}/{chapter_slug}')
    imgs = await tab.query(
        CHAPTER_IMAGE_SELECTOR,
        find_all=True,
        timeout=SCRAPE_TIMEOUT,
        raise_exc=False,
    )
    if not imgs:
        return []

    data_uris = await asyncio.gather(
        *[fetch_image_data_uri_from_element(img) for img in imgs]
    )
    # Keep one slot per DOM img; failed fetches become '' to preserve page order.
    return [uri or '' for uri in data_uris]


async def scrape_chapter_pages(manga_slug: str, chapter_slug: str) -> list[str]:
    options = get_chrome_options()

    async with Chrome(options=options) as browser:
        tab = await start_tab(browser)
        return await scrape_chapter_pages_on_tab(tab, manga_slug, chapter_slug)


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
