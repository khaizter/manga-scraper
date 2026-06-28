"""Unit tests for pending chapter selection rules."""

from datetime import datetime, timezone

from app.pipeline.chapter_selection import (
    pending_chapters_for_manga,
    select_pending_chapters,
)
from app.pipeline.models import ChapterDocument, MangaDocument, ScrapeStatus


def _manga(
    slug: str, chapters: list[str], *, discovered_at: datetime, status: ScrapeStatus
) -> MangaDocument:
    return MangaDocument(
        slug=slug,
        chapters=chapters,
        scrape_status=status,
        discovered_at=discovered_at,
        created_at=discovered_at,
        updated_at=discovered_at,
    )


def _chapter(
    number: str, *, status: ScrapeStatus = ScrapeStatus.PENDING
) -> ChapterDocument:
    return ChapterDocument(
        chapter_number=number,
        chapter_slug=f"chapter-{number}",
        scrape_status=status,
    )


class TestPendingChaptersForManga:
    def test_should_return_unsynced_chapters_in_manga_list_order(self) -> None:
        """Should follow manga.chapters order and skip already synced chapters."""
        manga = _manga(
            "black-clover",
            ["3", "1", "2"],
            discovered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            status=ScrapeStatus.SYNCED,
        )
        existing = {
            "1": _chapter("1", status=ScrapeStatus.SYNCED),
            "2": _chapter("2", status=ScrapeStatus.PENDING),
            "3": _chapter("3", status=ScrapeStatus.FAILED),
        }

        pending = pending_chapters_for_manga(manga, existing)

        assert [item.chapter.chapter_number for item in pending] == ["3", "2"]

    def test_should_create_pending_stub_when_chapter_subdoc_is_missing(self) -> None:
        """Should treat a missing Firestore subdoc as a pending chapter stub."""
        manga = _manga(
            "black-clover",
            ["99"],
            discovered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            status=ScrapeStatus.SYNCED,
        )

        pending = pending_chapters_for_manga(manga, {})

        assert len(pending) == 1
        assert pending[0].chapter.chapter_number == "99"
        assert pending[0].chapter.chapter_slug == "chapter-99"
        assert pending[0].chapter.scrape_status == ScrapeStatus.PENDING


class TestSelectPendingChapters:
    def test_should_process_oldest_discovered_manga_first(self) -> None:
        """Should sort by discoveredAt before walking each manga's chapter list."""
        older = _manga(
            "older",
            ["1"],
            discovered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            status=ScrapeStatus.SYNCED,
        )
        newer = _manga(
            "newer",
            ["1"],
            discovered_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            status=ScrapeStatus.SYNCED,
        )

        pending = select_pending_chapters(
            [newer, older],
            {
                "older": {},
                "newer": {},
            },
            limit=10,
        )

        assert [item.manga_slug for item in pending] == ["older", "newer"]

    def test_should_skip_manga_that_is_not_synced(self) -> None:
        """Should only select chapters from mangas with scrapeStatus synced."""
        pending_manga = _manga(
            "pending-manga",
            ["1"],
            discovered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            status=ScrapeStatus.PENDING,
        )
        synced_manga = _manga(
            "synced-manga",
            ["1"],
            discovered_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            status=ScrapeStatus.SYNCED,
        )

        pending = select_pending_chapters(
            [pending_manga, synced_manga],
            {"synced-manga": {}},
            limit=10,
        )

        assert len(pending) == 1
        assert pending[0].manga_slug == "synced-manga"

    def test_should_stop_after_reaching_limit(self) -> None:
        """Should return at most limit chapters across all eligible mangas."""
        manga_a = _manga(
            "a",
            ["1", "2"],
            discovered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            status=ScrapeStatus.SYNCED,
        )
        manga_b = _manga(
            "b",
            ["1"],
            discovered_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            status=ScrapeStatus.SYNCED,
        )

        pending = select_pending_chapters(
            [manga_a, manga_b],
            {"a": {}, "b": {}},
            limit=2,
        )

        assert len(pending) == 2
        assert pending[0].manga_slug == "a"
        assert pending[1].manga_slug == "a"
