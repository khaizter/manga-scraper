"""Unit tests for the manga chapters API client."""

import pytest
from aioresponses import aioresponses

from app.core.config import CHAPTERS_API_URL
from app.services.chapters_api import fetch_chapter_numbers, to_chapter_number


class TestToChapterNumber:
    @pytest.mark.parametrize(
        ("slug", "expected"),
        [
            ("chapter-336-1", "336-1"),
            ("chapter-1", "1"),
            ("336-1", "336-1"),
        ],
        ids=[
            "strips chapter prefix from slug",
            "strips prefix from simple chapter",
            "leaves bare chapter number unchanged",
        ],
    )
    def test_should_normalize_chapter_slug(self, slug: str, expected: str) -> None:
        """Should convert API chapter_slug values into chapter numbers."""
        assert to_chapter_number(slug) == expected


class TestFetchChapterNumbers:
    @pytest.mark.asyncio
    async def test_should_return_chapter_numbers_on_success(self) -> None:
        """Should parse chapter numbers from a successful API response."""
        url = CHAPTERS_API_URL.format(slug="black-clover")
        payload = {
            "success": True,
            "data": {
                "chapters": [
                    {"chapter_slug": "chapter-336-1"},
                    {"chapter_slug": "chapter-335"},
                ],
            },
        }

        with aioresponses() as mocked:
            mocked.get(url, payload=payload)
            chapters = await fetch_chapter_numbers("black-clover")

        assert chapters == ["336-1", "335"]

    @pytest.mark.asyncio
    async def test_should_return_empty_list_when_success_is_false(self) -> None:
        """Should return an empty list when the API reports success=false."""
        url = CHAPTERS_API_URL.format(slug="black-clover")

        with aioresponses() as mocked:
            mocked.get(url, payload={"success": False})
            chapters = await fetch_chapter_numbers("black-clover")

        assert chapters == []

    @pytest.mark.asyncio
    async def test_should_skip_chapters_without_slug(self) -> None:
        """Should ignore chapter entries that do not include chapter_slug."""
        url = CHAPTERS_API_URL.format(slug="black-clover")
        payload = {
            "success": True,
            "data": {
                "chapters": [
                    {"chapter_slug": "chapter-1"},
                    {},
                    {"chapter_slug": "chapter-2"},
                ],
            },
        }

        with aioresponses() as mocked:
            mocked.get(url, payload=payload)
            chapters = await fetch_chapter_numbers("black-clover")

        assert chapters == ["1", "2"]
