from app.core.config import BASE_URL
from app.pipeline.models import ChapterDocument, MangaDocument, ScrapeStatus
from app.pipeline.sync_manga.types import MangaExtractResult, SyncMangaLoadItem
from app.services.chapters_api import CHAPTER_SLUG_PREFIX


def build_chapter_documents(chapters: list[str]) -> list[ChapterDocument]:
    return [
        ChapterDocument(
            chapter_number=number,
            chapter_slug=f'{CHAPTER_SLUG_PREFIX}{number}',
            scrape_status=ScrapeStatus.PENDING,
        )
        for number in chapters
    ]


def transform_manga(extract: MangaExtractResult, existing: MangaDocument) -> SyncMangaLoadItem:
    """Shape scraped data into documents ready to load."""
    manga = MangaDocument.from_scrape(
        slug=extract.slug,
        data={**extract.detail, 'chapters': extract.chapters},
        source_url=f'{BASE_URL}/manga/{extract.slug}',
    )
    manga.created_at = existing.created_at
    manga.discovered_at = existing.discovered_at
    manga.attempts = 0
    manga.last_error = None

    return SyncMangaLoadItem(
        manga=manga,
        chapters=build_chapter_documents(manga.chapters),
        cover_data_uri=extract.detail.get('imageDataUri') or None,
    )
