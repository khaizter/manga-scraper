import asyncio
import json
import sys

import typer

from image_scraper import BASE_URL
from scrape_manga import scrape_manga
from scrape_manga_chapter import scrape_manga_chapter
from scrape_manga_list import LIST_URL, scrape_manga_list

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

app = typer.Typer(help='Scrape manga from mangakakalot.gg')


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
    detail = asyncio.run(scrape_manga(slug))
    payload = {'slug': slug, **detail}
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


@app.command('chapter')
def manga_chapter(
    manga_slug: str = typer.Argument(help='Manga slug, e.g. black-clover'),
    chapter_slug: str = typer.Argument(help='Chapter slug, e.g. chapter-336-1'),
) -> None:
    """Scrape chapter page images by manga and chapter slug."""
    typer.echo(f'Scraping {BASE_URL}/manga/{manga_slug}/{chapter_slug} ...')
    result = asyncio.run(scrape_manga_chapter(manga_slug, chapter_slug))

    if not result['pages']:
        typer.echo('No chapter images found.', err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Found {len(result['pages'])} page(s):\n")
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    app()
