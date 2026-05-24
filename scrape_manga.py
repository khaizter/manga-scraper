from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.extractor import ExtractionModel, Field

BASE_URL = 'https://www.mangakakalot.gg'


def strip_label_value(text: str) -> str:
    if ':' in text:
        return text.split(':', 1)[1].strip()
    return text.strip()


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
        description='Chapter titles',
    )


async def scrape_manga(slug: str) -> MangaDetail:
    options = ChromiumOptions()

    async with Chrome(options=options) as browser:
        tab = await browser.start()
        await tab.go_to(f'{BASE_URL}/manga/{slug}')
        return await tab.extract(MangaDetail, timeout=30)
