from typing import Any

from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions

from image_scraper import BASE_URL, fetch_images_from_selector

CHAPTER_IMAGE_SELECTOR = 'div.container-chapter-reader img'


async def scrape_manga_chapter(manga_slug: str, chapter_slug: str) -> dict[str, Any]:
    options = ChromiumOptions()
    url = f'{BASE_URL}/manga/{manga_slug}/{chapter_slug}'

    async with Chrome(options=options) as browser:
        tab = await browser.start()
        await tab.go_to(url)
        pages = await fetch_images_from_selector(tab, CHAPTER_IMAGE_SELECTOR, timeout=30)

    return {
        'mangaSlug': manga_slug,
        'chapterSlug': chapter_slug,
        'pages': pages,
    }
