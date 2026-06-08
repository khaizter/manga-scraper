from app.core.config import BASE_URL
from app.pipeline.models import ChapterDocument, DiscoverResult, ScrapeStatus, SyncMangasResult
from app.services.chapters_api import CHAPTER_SLUG_PREFIX
from app.services.manga import sync_mangas_in_session
from app.services.manga_list import discover_slugs_from_pages


async def discover_mangas_from_pages(
    start_page: int,
    end_page: int,
    *,
    delay_seconds: float = 2.0,
) -> DiscoverResult:
    return await discover_slugs_from_pages(
        start_page,
        end_page,
        delay_seconds=delay_seconds,
    )


async def sync_mangas_from_slugs(
    slugs: list[str],
    *,
    delay_seconds: float = 30.0,
) -> SyncMangasResult:
    return await sync_mangas_in_session(slugs, delay_seconds=delay_seconds)


def build_chapter_documents(chapter_numbers: list[str]) -> list[ChapterDocument]:
    return [
        ChapterDocument(
            chapter_number=number,
            chapter_slug=f'{CHAPTER_SLUG_PREFIX}{number}',
            scrape_status=ScrapeStatus.PENDING,
        )
        for number in chapter_numbers
    ]
