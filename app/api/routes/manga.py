from fastapi import APIRouter, HTTPException

from app.schemas.manga import (
    MangaChapterResponse,
    MangaDetailResponse,
    MangaListItemResponse,
    MangaListRequest,
    MangaListResponse,
)
from app.services.scrape_chapter_pages import get_manga_chapter
from app.services.scrape_manga_details import get_manga
from app.services.scrape_manga_slugs import get_manga_list

router = APIRouter(prefix='/api', tags=['mangas'])


def to_chapter_slug(chapter_number: str) -> str:
    return f'chapter-{chapter_number}'


@router.post('/mangas', response_model=MangaListResponse)
async def manga_list(body: MangaListRequest) -> MangaListResponse:
    result = await get_manga_list(body.page)

    if not result['items']:
        raise HTTPException(status_code=404, detail='No manga found on this page')

    return MangaListResponse(
        currentPage=body.page,
        totalPages=result['totalPages'],
        items=[MangaListItemResponse.model_validate(item) for item in result['items']],
    )


@router.get('/mangas/{slug}/chapter/{chapter_number}', response_model=MangaChapterResponse)
async def manga_chapter(slug: str, chapter_number: str) -> MangaChapterResponse:
    chapter_slug = to_chapter_slug(chapter_number)
    result = await get_manga_chapter(slug, chapter_slug)

    if not result['pages']:
        raise HTTPException(status_code=404, detail='No chapter images found')

    return MangaChapterResponse.model_validate({
        **result,
        'chapterSlug': chapter_number,
    })


@router.get('/mangas/{slug}', response_model=MangaDetailResponse)
async def manga_detail(slug: str) -> MangaDetailResponse:
    detail = await get_manga(slug)
    return MangaDetailResponse(slug=slug, **detail)
