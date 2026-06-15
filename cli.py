import asyncio
import json
import logging
import sys

import typer

from app.core.env import load_env

load_env()

from app.core.config import BASE_URL, LIST_URL
from app.pipeline.runner import PipelineRunner
from app.services.scrape_chapter_pages import get_manga_chapter
from app.services.scrape_manga_details import get_manga
from app.services.scrape_manga_slugs import get_manga_list

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

app = typer.Typer(help='Scrape manga from mangakakalot.gg')
pipeline_app = typer.Typer(help='Batch pipeline for discovery and sync')
app.add_typer(pipeline_app, name='pipeline')


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
    result = asyncio.run(get_manga_list(page))
    mangas = result['items']

    if not mangas:
        typer.echo('No manga found on this page.', err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Found {len(mangas)} manga (total pages: {result['totalPages']}):\n")
    for manga in mangas:
        typer.echo(f"{manga['title']}: {manga['slug']}")
        typer.echo(json.dumps(manga, ensure_ascii=False))


@app.command('detail')
def manga_detail(
    slug: str = typer.Argument(help='Manga slug, e.g. double-the-trouble-twice-as-nice'),
) -> None:
    """Scrape manga details by slug."""
    typer.echo(f'Scraping {BASE_URL}/manga/{slug} ...')
    detail = asyncio.run(get_manga(slug))
    payload = {'slug': slug, **detail}
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


@app.command('chapter')
def manga_chapter(
    manga_slug: str = typer.Argument(help='Manga slug, e.g. black-clover'),
    chapter_slug: str = typer.Argument(help='Chapter slug, e.g. chapter-336-1'),
) -> None:
    """Scrape chapter page images by manga and chapter slug."""
    typer.echo(f'Scraping {BASE_URL}/manga/{manga_slug}/{chapter_slug} ...')
    result = asyncio.run(get_manga_chapter(manga_slug, chapter_slug))

    if not result['pages']:
        typer.echo('No chapter images found.', err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Found {len(result['pages'])} page(s):\n")
    typer.echo(json.dumps(result, indent=2, ensure_ascii=False))


@pipeline_app.command('discover')
def pipeline_discover(
    start_page: int = typer.Option(1, '--start-page', help='First listing page to scan'),
    page_count: int = typer.Option(1, '--page-count', '-n', help='Number of listing pages to scan'),
    delay: float = typer.Option(2.0, '--delay', help='Seconds between page navigations'),
    dry_run: bool = typer.Option(False, '--dry-run', help='Scrape pages without enqueueing manga stubs'),
    verbose: bool = typer.Option(False, '--verbose', '-v', help='Log detailed progress'),
) -> None:
    """Discover manga slugs from listing pages and create pending manga stubs."""
    runner = PipelineRunner()
    stats = asyncio.run(
        runner.discover(
            start_page=start_page,
            page_count=page_count,
            delay_seconds=delay,
            dry_run=dry_run,
            verbose=verbose,
        )
    )
    typer.echo(json.dumps(stats, indent=2, default=str))


@pipeline_app.command('sync-manga')
def pipeline_sync_manga(
    limit: int = typer.Option(10, '--limit', '-n', help='Max mangas to sync this run'),
    delay: float = typer.Option(30.0, '--delay', help='Seconds between manga scrapes'),
    dry_run: bool = typer.Option(False, '--dry-run', help='Scrape mangas without writing to Firestore/Storage'),
    verbose: bool = typer.Option(False, '--verbose', '-v', help='Log detailed progress'),
) -> None:
    """Sync pending mangas (metadata + chapter list) with rate limiting."""
    runner = PipelineRunner(delay_seconds=delay)
    stats = asyncio.run(
        runner.sync_mangas(limit=limit, dry_run=dry_run, verbose=verbose),
    )
    typer.echo(json.dumps(stats, indent=2, default=str))


@pipeline_app.command('sync-chapters')
def pipeline_sync_chapters(
    limit: int = typer.Option(10, '--limit', '-n', help='Max chapters to sync this run'),
    delay: float = typer.Option(30.0, '--delay', help='Seconds between chapter scrapes'),
    dry_run: bool = typer.Option(False, '--dry-run', help='Scrape chapters without uploading pages'),
    verbose: bool = typer.Option(False, '--verbose', '-v', help='Log detailed progress'),
) -> None:
    """Sync chapter page images for synced mangas with pending chapter uploads."""
    runner = PipelineRunner(delay_seconds=delay)
    stats = asyncio.run(
        runner.sync_chapters(limit=limit, dry_run=dry_run, verbose=verbose),
    )
    typer.echo(json.dumps(stats, indent=2, default=str))


@pipeline_app.command('status')
def pipeline_status() -> None:
    """Show manga and chapter scrape status counts."""
    runner = PipelineRunner()
    typer.echo(json.dumps(asyncio.run(runner.status()), indent=2, default=str))


if __name__ == '__main__':
    app()
