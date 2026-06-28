"""Unit tests for image URL and data URI helpers."""

import base64

from app.utils.image import (
    build_image_data_uri,
    image_mime_type,
    normalize_image_url,
)


class TestNormalizeImageUrl:
    def test_should_prefix_protocol_relative_urls_with_https(self) -> None:
        """Should turn //host/path URLs into https://host/path."""
        assert (
            normalize_image_url("//cdn.example.com/a.webp")
            == "https://cdn.example.com/a.webp"
        )

    def test_should_resolve_root_relative_urls_against_base_url(self) -> None:
        """Should join /path URLs to the manga site base URL."""
        assert (
            normalize_image_url("/images/cover.jpg")
            == "https://www.mangakakalot.gg/images/cover.jpg"
        )

    def test_should_leave_absolute_urls_unchanged(self) -> None:
        """Should not modify already absolute URLs."""
        url = "https://cdn.example.com/page.png"
        assert normalize_image_url(url) == url


class TestImageMimeType:
    def test_should_detect_mime_from_file_extension(self) -> None:
        """Should map common image extensions to mime types."""
        assert image_mime_type("https://example.com/page.webp") == "image/webp"
        assert image_mime_type("https://example.com/page.JPG") == "image/jpeg"
        assert image_mime_type("https://example.com/unknown") == "image/jpeg"


class TestBuildImageDataUri:
    def test_should_build_data_uri_with_matching_mime(self) -> None:
        """Should embed base64 image data with the mime type from the source URL."""
        encoded = base64.b64encode(b"img").decode("ascii")
        uri = build_image_data_uri(encoded, "https://example.com/a.webp")

        assert uri == f"data:image/webp;base64,{encoded}"
