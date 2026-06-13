from pydantic import BaseModel, Field

from app.pipeline.types import PipelineOptions


class DiscoverInput(PipelineOptions):
    start_page: int = 1
    page_count: int = 1

    @property
    def end_page(self) -> int:
        return self.start_page + self.page_count - 1


class PageExtractResult(BaseModel):
    page: int
    slugs: list[str] = Field(default_factory=list)
    success: bool
    error: str | None = None


class DiscoverLoadBatch(BaseModel):
    page: int
    slugs: list[str] = Field(default_factory=list)
    success: bool
    error: str | None = None
