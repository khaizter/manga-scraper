from pydantic import BaseModel, Field

from app.pipeline.models import ChapterDocument, PendingChapter
from app.pipeline.types import PipelineOptions


class SyncChapterInput(PipelineOptions):
    limit: int = 10


class ChapterExtractResult(BaseModel):
    manga_slug: str
    chapter: ChapterDocument
    page_data_uris: list[str] = Field(default_factory=list)


class PageUpload(BaseModel):
    storage_path: str
    data: bytes
    content_type: str


class SyncChapterLoadItem(BaseModel):
    manga_slug: str
    chapter: ChapterDocument
    pages: list[PageUpload] = Field(default_factory=list)
