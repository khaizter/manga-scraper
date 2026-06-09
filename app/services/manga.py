import asyncio
import logging
import re
from typing import Any

from pydoll.browser.chromium import Chrome
from pydoll.browser.tab import Tab
from pydoll.extractor import ExtractionModel, Field

from app.core.browser import get_chrome_options, navigate_to, start_tab
from app.core.config import BASE_URL, SCRAPE_TIMEOUT
from app.pipeline.config import PIPELINE_STORE
from app.pipeline.models import MangaDocument, SyncMangaResult, SyncMangasResult
from app.services.chapters_api import fetch_chapter_numbers
from app.services.storage import upload_manga_cover
from app.utils.image import fetch_image_data_uri_from_element

logger = logging.getLogger(__name__)

COVER_IMAGE_SELECTOR = 'div.manga-info-pic img'


def strip_label_value(text: str) -> str:
    if ':' in text:
        return text.split(':', 1)[1].strip()
    return text.strip()


def strip_summary_heading(text: str) -> str:
    return re.sub(r'^[^\n]*summary:\s*\n*', '', text, flags=re.IGNORECASE).strip()


class MangaDetail(ExtractionModel):
    title: str = Field(
        selector='ul.manga-info-text li:nth-child(1) h1',
        description='Manga title',
    )
    description: str = Field(
        selector='div#contentBox',
        description='Manga synopsis',
        transform=strip_summary_heading,
        default='',
    )
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


async def get_cover_image(tab: Tab) -> str:
    img = await tab.query(COVER_IMAGE_SELECTOR, timeout=SCRAPE_TIMEOUT)
    image_data_uri = await fetch_image_data_uri_from_element(img)
    return image_data_uri or ''


async def scrape_manga_detail_on_tab(tab: Tab, slug: str) -> dict[str, Any]:
    await navigate_to(tab, f'{BASE_URL}/manga/{slug}')
    detail = await tab.extract(MangaDetail, timeout=SCRAPE_TIMEOUT)
    cover = await get_cover_image(tab)
    return {
        **detail.model_dump(),
        'imageDataUri': cover,
    }


async def scrape_manga_detail(slug: str) -> dict[str, Any]:
    options = get_chrome_options()

    async with Chrome(options=options) as browser:
        tab = await start_tab(browser)
        return await scrape_manga_detail_on_tab(tab, slug)


async def sync_manga_on_tab(tab: Tab, slug: str) -> MangaDocument:
    detail, chapters = await asyncio.gather(
        scrape_manga_detail_on_tab(tab, slug),
        fetch_chapter_numbers(slug),
    )

    cover_storage_path: str | None = None
    image_data_uri = detail.get('imageDataUri') or ''
    if image_data_uri and PIPELINE_STORE == 'firestore':
        try:
            cover_storage_path = await upload_manga_cover(slug, image_data_uri)
        except Exception as exc:
            logger.warning('Failed to upload cover for %s: %s', slug, exc)

    return MangaDocument.from_scrape(
        slug=slug,
        data={**detail, 'chapters': chapters},
        source_url=f'{BASE_URL}/manga/{slug}',
        cover_storage_path=cover_storage_path,
    )


async def sync_mangas_in_session(
    slugs: list[str],
    *,
    delay_seconds: float = 30.0,
) -> SyncMangasResult:
    """Sync multiple mangas using a single browser session."""
    results: list[SyncMangaResult] = []
    options = get_chrome_options()

    async with Chrome(options=options) as browser:
        tab = await start_tab(browser)
        for index, slug in enumerate(slugs):
            try:
                manga = await sync_manga_on_tab(tab, slug)
                results.append(SyncMangaResult(slug=slug, manga=manga, success=True))
                logger.info('Synced manga: %s (%d chapters)', slug, len(manga.chapters))
            except Exception as exc:
                error = str(exc)
                results.append(
                    SyncMangaResult(slug=slug, manga=None, success=False, error=error),
                )
                logger.error('Failed to sync manga %s: %s', slug, error, exc_info=True)

            if index < len(slugs) - 1:
                await asyncio.sleep(delay_seconds)

    return SyncMangasResult(results=results)


async def get_manga(slug: str) -> dict[str, Any]:
    detail, chapters = await asyncio.gather(
        scrape_manga_detail(slug),
        fetch_chapter_numbers(slug),
    )

    return {
        **detail,
        'chapters': chapters,
    }
