from typing import Any

from pydoll.browser.chromium import Chrome

from app.core.browser import get_chrome_options
from app.core.config import BASE_URL, SCRAPE_TIMEOUT
from app.utils.image import fetch_image_data_uris_from_selector

CHAPTER_IMAGE_SELECTOR = 'div.container-chapter-reader img'


async def get_manga_chapter(manga_slug: str, chapter_slug: str) -> dict[str, Any]:
    options = get_chrome_options()
    url = f'{BASE_URL}/manga/{manga_slug}/{chapter_slug}'

    async with Chrome(options=options) as browser:
        tab = await browser.start()
        await tab.go_to(url)
        pages = await fetch_image_data_uris_from_selector(
            tab,
            CHAPTER_IMAGE_SELECTOR,
            timeout=SCRAPE_TIMEOUT,
        )

    return {
        'mangaSlug': manga_slug,
        'chapterSlug': chapter_slug,
        'pages': pages,
    }
