"""Unit tests for the discover pipeline transform stage."""

from app.pipeline.discover.transform import transform_page
from app.pipeline.discover.types import PageExtractResult


class TestTransformPage:
    def test_should_map_successful_page_extract_to_load_batch(self) -> None:
        """Should preserve page number, slugs, and success flag."""
        result = PageExtractResult(
            page=2,
            slugs=["black-clover", "one-piece"],
            success=True,
        )

        batch = transform_page(result)

        assert batch.page == 2
        assert batch.slugs == ["black-clover", "one-piece"]
        assert batch.success is True
        assert batch.error is None

    def test_should_preserve_error_on_failed_page_extract(self) -> None:
        """Should carry through the failure error message."""
        result = PageExtractResult(page=5, slugs=[], success=False, error="timeout")

        batch = transform_page(result)

        assert batch.success is False
        assert batch.error == "timeout"
