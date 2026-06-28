"""Unit tests for the sync-manga pipeline transform stage."""

from datetime import datetime, timezone

from app.pipeline.models import MangaDocument, ScrapeStatus
from app.pipeline.sync_manga.transform import build_chapter_documents, transform_manga
from app.pipeline.sync_manga.types import MangaExtractResult


class TestBuildChapterDocuments:
    def test_should_create_pending_chapter_subdocs(self) -> None:
        """Should build chapter documents with chapter- prefixed slugs."""
        chapters = build_chapter_documents(["336-1", "335"])

        assert len(chapters) == 2
        assert chapters[0].chapter_number == "336-1"
        assert chapters[0].chapter_slug == "chapter-336-1"
        assert chapters[0].scrape_status == ScrapeStatus.PENDING


class TestTransformManga:
    def test_should_preserve_discovery_metadata_from_existing_stub(self) -> None:
        """Should keep discoveredAt and createdAt while marking the manga synced."""
        discovered = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
        created = datetime(2026, 1, 10, 8, 0, tzinfo=timezone.utc)
        existing = MangaDocument(
            slug="black-clover",
            scrape_status=ScrapeStatus.PENDING,
            discovered_at=discovered,
            created_at=created,
            updated_at=created,
        )
        extract = MangaExtractResult(
            slug="black-clover",
            detail={
                "title": "Black Clover",
                "description": "Asta wants to be Wizard King.",
                "author": "Yuki Tabata",
                "status": "Ongoing",
                "imageDataUri": "data:image/jpeg;base64,abc",
            },
            chapters=["336-1", "335"],
        )

        item = transform_manga(extract, existing)

        assert item.manga.slug == "black-clover"
        assert item.manga.title == "Black Clover"
        assert item.manga.scrape_status == ScrapeStatus.SYNCED
        assert item.manga.discovered_at == discovered
        assert item.manga.created_at == created
        assert item.manga.attempts == 0
        assert item.manga.last_error is None
        assert item.manga.source_url == "https://www.mangakakalot.gg/manga/black-clover"
        assert item.cover_data_uri == "data:image/jpeg;base64,abc"
        assert len(item.chapters) == 2
