"""Unit tests for pipeline models and storage path helpers."""

from app.pipeline.models import (
    JobStatus,
    MangaDocument,
    ScrapeStatus,
    chapter_page_storage_path,
    manga_cover_storage_path,
    resolve_job_status,
)


class TestMangaDocument:
    def test_should_create_pending_stub_with_defaults(self) -> None:
        """Should create a manga stub with pending scrape status and no chapters."""
        doc = MangaDocument.pending_stub("black-clover")

        assert doc.slug == "black-clover"
        assert doc.title is None
        assert doc.scrape_status == ScrapeStatus.PENDING
        assert doc.chapters == []
        assert doc.attempts == 0

    def test_should_build_synced_document_from_scrape_data(self) -> None:
        """Should map scraped fields and mark the manga as synced."""
        doc = MangaDocument.from_scrape(
            slug="black-clover",
            data={
                "title": "Black Clover",
                "description": "",
                "author": "Yuki Tabata",
                "status": "Ongoing",
                "chapters": ["1", "2"],
            },
            source_url="https://www.mangakakalot.gg/manga/black-clover",
        )

        assert doc.title == "Black Clover"
        assert doc.description is None
        assert doc.chapters == ["1", "2"]
        assert doc.scrape_status == ScrapeStatus.SYNCED
        assert doc.last_synced_at is not None

    def test_should_serialize_firestore_field_aliases(self) -> None:
        """Should export camelCase keys expected by Firestore."""
        doc = MangaDocument.pending_stub("black-clover")
        payload = doc.model_dump(by_alias=True)

        assert "scrapeStatus" in payload
        assert "discoveredAt" in payload
        assert "scrape_status" not in payload


class TestStoragePaths:
    def test_should_build_cover_and_chapter_page_paths(self) -> None:
        """Should produce lowercase storage paths under mangas/{slug}."""
        assert (
            manga_cover_storage_path("black-clover", "webp")
            == "mangas/black-clover/cover.webp"
        )
        assert (
            chapter_page_storage_path("black-clover", "336-1", 0, "webp")
            == "mangas/black-clover/chapters/336-1/0.webp"
        )


class TestResolveJobStatus:
    def test_should_return_completed_when_all_items_succeed(self) -> None:
        """Should return completed when there are no failures."""
        assert resolve_job_status(3, 0) == JobStatus.COMPLETED

    def test_should_return_failed_when_all_items_fail(self) -> None:
        """Should return failed when nothing succeeded."""
        assert resolve_job_status(0, 2) == JobStatus.FAILED

    def test_should_return_partially_completed_on_mixed_results(self) -> None:
        """Should return partially_completed when some items succeed and some fail."""
        assert resolve_job_status(2, 1) == JobStatus.PARTIALLY_COMPLETED
