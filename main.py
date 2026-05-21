import asyncio
import sys
from typing import Optional
from urllib.parse import urlparse

from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.extractor import ExtractionModel, Field

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def extract_slug(url: str) -> str:
    path = urlparse(url).path.rstrip('/')
    prefix = '/manga/'
    if path.startswith(prefix):
        return path[len(prefix):]
    return path.split('/')[-1]

class Manga(ExtractionModel):
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


async def main():
    options = ChromiumOptions()

    async with Chrome(options=options) as browser:
        tab = await browser.start()
        await tab.go_to('https://www.mangakakalot.gg/genre/all?page=1')

        mangas = await tab.extract_all(
            Manga,
            scope='div.comic-list div.list-comic-item-wrap',
            timeout=30,
        )

        for manga in mangas:
            print(f'{manga.title}: {manga.slug}')
            print(manga.model_dump_json())


if __name__ == '__main__':
    asyncio.run(main())
