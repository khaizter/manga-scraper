from typing import Any

from pydoll.browser.chromium import Chrome
from pydoll.browser.tab import Tab
from pydoll.extractor import ExtractionModel, Field

from app.core.browser import get_chrome_options
from app.core.config import BASE_URL, SCRAPE_TIMEOUT
from app.utils.image import fetch_image_payload_from_element

COVER_IMAGE_SELECTOR = 'div.manga-info-pic img'


def strip_label_value(text: str) -> str:
    if ':' in text:
        return text.split(':', 1)[1].strip()
    return text.strip()


def chapter_to_slug(text: str) -> str:
    return text.strip().lower().replace('.', '-').replace(' ', '-')


class MangaDetail(ExtractionModel):
    author: str = Field(
        selector='ul.manga-info-text li:nth-child(2)',
        description='Manga author',
        transform=strip_label_value,
    )
    status: str = Field(
        selector='ul.manga-info-text li:nth-child(3)',
        description='Manga status',
        transform=strip_label_value,
    )
    chapters: list[str] = Field(
        selector='div.chapter-list div.row span a',
        description='Chapter slugs',
        transform=chapter_to_slug,
    )


async def get_cover_image(tab: Tab) -> dict[str, str]:
    img = await tab.query(COVER_IMAGE_SELECTOR, timeout=SCRAPE_TIMEOUT)
    payload = await fetch_image_payload_from_element(img)
    return payload or {'image': '', 'imageDataUri': ''}


async def get_manga(slug: str) -> dict[str, Any]:
    options = get_chrome_options()

    async with Chrome(options=options) as browser:
        tab = await browser.start()
        await tab.go_to(f'{BASE_URL}/manga/{slug}')
        detail = await tab.extract(MangaDetail, timeout=SCRAPE_TIMEOUT)
        cover = await get_cover_image(tab)

    return {
        **detail.model_dump(),
        **cover,
    }
