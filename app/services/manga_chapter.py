import asyncio
from typing import Any

import aiohttp
from pydoll.browser.chromium import Chrome

from app.core.browser import get_chrome_options, navigate_to, start_tab
from app.core.config import BASE_URL, CHAPTERS_API_URL, SCRAPE_TIMEOUT
from app.utils.image import DEFAULT_HEADERS, fetch_image_data_uris_from_selector

CHAPTER_IMAGE_SELECTOR = 'div.container-chapter-reader > img'


async def fetch_chapter_slugs(manga_slug: str) -> list[str]:
    url = CHAPTERS_API_URL.format(slug=manga_slug)

    async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            payload = await response.json()

    if not payload.get('success'):
        return []

    chapters = payload.get('data', {}).get('chapters', [])
    return [chapter['chapter_slug'] for chapter in chapters if chapter.get('chapter_slug')]


async def scrape_chapter_pages(manga_slug: str, chapter_slug: str) -> list[str]:
    url = f'{BASE_URL}/manga/{manga_slug}/{chapter_slug}'
    options = get_chrome_options()

    async with Chrome(options=options) as browser:
        tab = await start_tab(browser)
        await navigate_to(tab, url)
        return await fetch_image_data_uris_from_selector(
            tab,
            CHAPTER_IMAGE_SELECTOR,
            timeout=SCRAPE_TIMEOUT,
        )


async def get_manga_chapter(manga_slug: str, chapter_slug: str) -> dict[str, Any]:
    pages, chapters = await asyncio.gather(
        scrape_chapter_pages(manga_slug, chapter_slug),
        fetch_chapter_slugs(manga_slug),
    )

    return {
        'mangaSlug': manga_slug,
        'chapterSlug': chapter_slug,
        'chapters': chapters,
        'pages': pages,
    }
