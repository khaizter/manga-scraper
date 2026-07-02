"""Unit tests for the manga chapters API client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.chapters_api import fetch_chapter_numbers, to_chapter_number


def _mock_http_json(payload: dict) -> MagicMock:
    """Build mocks for `async with http_session() as session: async with session.get()`."""
    response = AsyncMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=payload)

    get_context = AsyncMock()
    get_context.__aenter__ = AsyncMock(return_value=response)
    get_context.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock()
    session.get = MagicMock(return_value=get_context)

    session_context = AsyncMock()
    session_context.__aenter__ = AsyncMock(return_value=session)
    session_context.__aexit__ = AsyncMock(return_value=None)

    return session_context


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
        payload = {
            "success": True,
            "data": {
                "chapters": [
                    {"chapter_slug": "chapter-336-1"},
                    {"chapter_slug": "chapter-335"},
                ],
            },
        }

        with patch(
            "app.services.chapters_api.http_session",
            return_value=_mock_http_json(payload),
        ):
            chapters = await fetch_chapter_numbers("black-clover")

        assert chapters == ["336-1", "335"]

    @pytest.mark.asyncio
    async def test_should_return_empty_list_when_success_is_false(self) -> None:
        """Should return an empty list when the API reports success=false."""
        with patch(
            "app.services.chapters_api.http_session",
            return_value=_mock_http_json({"success": False}),
        ):
            chapters = await fetch_chapter_numbers("black-clover")

        assert chapters == []

    @pytest.mark.asyncio
    async def test_should_skip_chapters_without_slug(self) -> None:
        """Should ignore chapter entries that do not include chapter_slug."""
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

        with patch(
            "app.services.chapters_api.http_session",
            return_value=_mock_http_json(payload),
        ):
            chapters = await fetch_chapter_numbers("black-clover")

        assert chapters == ["1", "2"]
