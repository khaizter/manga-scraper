"""Unit tests for the sync-chapter pipeline transform stage."""

import base64

import pytest

from app.pipeline.models import ChapterDocument, ScrapeStatus
from app.pipeline.sync_chapter.transform import transform_chapter
from app.pipeline.sync_chapter.types import ChapterExtractResult


def _data_uri(mime: str, content: bytes) -> str:
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{mime};base64,{encoded}"


class TestTransformChapter:
    def test_should_build_storage_paths_and_upload_payloads(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should map each page to a Firebase Storage path and upload payload."""
        monkeypatch.setattr(
            "app.pipeline.sync_chapter.transform.PIPELINE_STORE", "firestore"
        )
        chapter = ChapterDocument(chapter_number="336-1", chapter_slug="chapter-336-1")
        extract = ChapterExtractResult(
            manga_slug="black-clover",
            chapter=chapter,
            page_data_uris=[
                _data_uri("image/webp", b"page-0"),
                _data_uri("image/png", b"page-1"),
            ],
        )

        item = transform_chapter(extract)

        assert item.manga_slug == "black-clover"
        assert item.chapter.scrape_status == ScrapeStatus.SYNCED
        assert item.chapter.storage_paths == [
            "mangas/black-clover/chapters/336-1/0.webp",
            "mangas/black-clover/chapters/336-1/1.png",
        ]
        assert len(item.pages) == 2
        assert item.pages[0].content_type == "image/webp"
        assert item.pages[1].data == b"page-1"

    def test_should_preserve_page_index_for_failed_images(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should keep empty storage paths for failed pages without shifting indices."""
        monkeypatch.setattr(
            "app.pipeline.sync_chapter.transform.PIPELINE_STORE", "firestore"
        )
        chapter = ChapterDocument(chapter_number="336-1", chapter_slug="chapter-336-1")
        extract = ChapterExtractResult(
            manga_slug="black-clover",
            chapter=chapter,
            page_data_uris=[
                _data_uri("image/webp", b"page-0"),
                "",
                _data_uri("image/png", b"page-2"),
            ],
        )

        item = transform_chapter(extract)

        assert item.chapter.storage_paths == [
            "mangas/black-clover/chapters/336-1/0.webp",
            "",
            "mangas/black-clover/chapters/336-1/2.png",
        ]
        assert len(item.pages) == 2
        assert item.pages[0].data == b"page-0"
        assert item.pages[1].data == b"page-2"

    def test_should_require_firestore_store(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should reject chapter uploads when PIPELINE_STORE is not firestore."""
        monkeypatch.setattr(
            "app.pipeline.sync_chapter.transform.PIPELINE_STORE", "json"
        )
        extract = ChapterExtractResult(
            manga_slug="black-clover",
            chapter=ChapterDocument(chapter_number="1", chapter_slug="chapter-1"),
            page_data_uris=[_data_uri("image/jpeg", b"x")],
        )

        with pytest.raises(ValueError, match="PIPELINE_STORE=firestore"):
            transform_chapter(extract)

    def test_should_require_at_least_one_page(self) -> None:
        """Should fail when no chapter page images were scraped."""
        extract = ChapterExtractResult(
            manga_slug="black-clover",
            chapter=ChapterDocument(chapter_number="1", chapter_slug="chapter-1"),
            page_data_uris=[],
        )

        with pytest.raises(ValueError, match="No chapter pages found"):
            transform_chapter(extract)
