import asyncio
import json
import sys
from typing import Optional
from urllib.parse import urlparse

import typer
from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.extractor import ExtractionModel, Field

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

app = typer.Typer(help='Scrape manga from mangakakalot.gg')

BASE_URL = 'https://www.mangakakalot.gg'
LIST_URL = f'{BASE_URL}/genre/all'


def extract_slug(url: str) -> str:
    path = urlparse(url).path.rstrip('/')
    prefix = '/manga/'
    if path.startswith(prefix):
        return path[len(prefix):]
    return path.split('/')[-1]


def strip_label_value(text: str) -> str:
    if ':' in text:
        return text.split(':', 1)[1].strip()
    return text.strip()


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


async def scrape_manga_detail(slug: str) -> MangaDetail:
    options = ChromiumOptions()

    async with Chrome(options=options) as browser:
        tab = await browser.start()
        await tab.go_to(f'{BASE_URL}/manga/{slug}')
        return await tab.extract(MangaDetail, timeout=30)


@app.command('list')
def list_manga(
    page: int = typer.Option(
        1,
        '--page',
        '-p',
        help='Genre listing page number',
    ),
) -> None:
    """Scrape manga from a genre listing page."""
    typer.echo(f'Scraping {LIST_URL}?page={page} ...')
    mangas = asyncio.run(scrape_manga_list(page))

    if not mangas:
        typer.echo('No manga found on this page.', err=True)
        raise typer.Exit(code=1)

    typer.echo(f'Found {len(mangas)} manga:\n')
    for manga in mangas:
        typer.echo(f'{manga.title}: {manga.slug}')
        typer.echo(manga.model_dump_json())


@app.command('detail')
def manga_detail(
    slug: str = typer.Argument(help='Manga slug, e.g. double-the-trouble-twice-as-nice'),
) -> None:
    """Scrape manga details by slug."""
    typer.echo(f'Scraping {BASE_URL}/manga/{slug} ...')
    detail = asyncio.run(scrape_manga_detail(slug))
    payload = {'slug': slug, **detail.model_dump()}
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    app()
