from typing import Any

from pydantic import BaseModel, Field

from app.pipeline.models import ChapterDocument, MangaDocument
from app.pipeline.types import PipelineOptions


class SyncMangaInput(PipelineOptions):
    limit: int = 10


class MangaExtractResult(BaseModel):
    slug: str
    detail: dict[str, Any]
    chapters: list[str] = Field(default_factory=list)


class SyncMangaLoadItem(BaseModel):
    manga: MangaDocument
    chapters: list[ChapterDocument] = Field(default_factory=list)
    cover_data_uri: str | None = None
