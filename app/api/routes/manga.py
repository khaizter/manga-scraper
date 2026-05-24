from fastapi import APIRouter, HTTPException

from app.schemas.manga import (
    MangaChapterResponse,
    MangaDetailResponse,
    MangaListItemResponse,
    MangaListRequest,
    MangaListResponse,
)
from app.services.manga import get_manga
from app.services.manga_chapter import get_manga_chapter
from app.services.manga_list import get_manga_list

router = APIRouter(prefix='/api', tags=['manga'])


@router.post('/mangaList', response_model=MangaListResponse)
async def manga_list(body: MangaListRequest) -> MangaListResponse:
    items = await get_manga_list(body.page)

    if not items:
        raise HTTPException(status_code=404, detail='No manga found on this page')

    return MangaListResponse(
        page=body.page,
        items=[MangaListItemResponse.model_validate(item) for item in items],
    )


@router.get('/manga/{slug}/{chapter_slug}', response_model=MangaChapterResponse)
async def manga_chapter(slug: str, chapter_slug: str) -> MangaChapterResponse:
    result = await get_manga_chapter(slug, chapter_slug)

    if not result['pages']:
        raise HTTPException(status_code=404, detail='No chapter images found')

    return MangaChapterResponse.model_validate(result)


@router.get('/manga/{slug}', response_model=MangaDetailResponse)
async def manga_detail(slug: str) -> MangaDetailResponse:
    detail = await get_manga(slug)
    return MangaDetailResponse(slug=slug, **detail)
