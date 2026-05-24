from typing import Optional
from urllib.parse import urlparse

from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.extractor import ExtractionModel, Field

BASE_URL = 'https://www.mangakakalot.gg'
LIST_URL = f'{BASE_URL}/genre/all'


def extract_slug(url: str) -> str:
    path = urlparse(url).path.rstrip('/')
    prefix = '/manga/'
    if path.startswith(prefix):
        return path[len(prefix):]
    return path.split('/')[-1]


class MangaListItem(ExtractionModel):
    title: str = Field(
        selector='h3 > a',
        description='Manga title',
    )
    slug: str = Field(
        selector='h3 > a',
        attribute='href',
        description='Manga slug from detail page URL',
        transform=extract_slug,
    )
    description: Optional[str] = Field(
        selector='p',
        description='Manga synopsis',
        default=None,
    )


async def scrape_manga_list(page: int = 1) -> list[MangaListItem]:
    options = ChromiumOptions()

    async with Chrome(options=options) as browser:
        tab = await browser.start()
        await tab.go_to(f'{LIST_URL}?page={page}')
        return await tab.extract_all(
            MangaListItem,
            scope='div.comic-list div.list-comic-item-wrap',
            timeout=30,
        )
