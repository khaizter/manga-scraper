from pydantic import BaseModel, Field


class MangaListRequest(BaseModel):
    page: int = Field(default=1, ge=1, description='Genre listing page number')


class MangaListItemResponse(BaseModel):
    title: str
    slug: str
    description: str | None = None
    imageDataUri: str


class MangaListResponse(BaseModel):
    page: int
    items: list[MangaListItemResponse]


class MangaDetailResponse(BaseModel):
    slug: str
    title: str
    description: str | None = None
    author: str
    status: str
    chapters: list[str]
    imageDataUri: str


class MangaChapterResponse(BaseModel):
    mangaSlug: str
    chapterSlug: str
    pages: list[str]
