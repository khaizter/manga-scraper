"""Unit tests for HTTP client proxy configuration."""

import pytest

from app.core.http_client import resolve_http_proxy
from app.core.proxy import set_proxy_enabled


class TestResolveHttpProxy:
    def test_should_return_none_when_env_is_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should connect directly when CHROME_PROXY_URL is not configured."""
        monkeypatch.delenv("CHROME_PROXY_URL", raising=False)
        assert resolve_http_proxy() is None

    def test_should_return_proxy_url_when_scheme_is_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should pass through a fully qualified proxy URL."""
        monkeypatch.setenv("CHROME_PROXY_URL", "http://user:pass@proxy.example:33335")
        assert resolve_http_proxy() == "http://user:pass@proxy.example:33335"

    def test_should_add_http_scheme_when_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should default bare host:port values to http://."""
        monkeypatch.setenv("CHROME_PROXY_URL", "user:pass@proxy.example:33335")
        assert resolve_http_proxy() == "http://user:pass@proxy.example:33335"

    def test_should_trim_surrounding_whitespace(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should ignore leading and trailing whitespace in CHROME_PROXY_URL."""
        monkeypatch.setenv("CHROME_PROXY_URL", "  http://proxy.example:8080  ")
        assert resolve_http_proxy() == "http://proxy.example:8080"

    def test_should_return_none_when_proxy_disabled_via_cli(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should ignore CHROME_PROXY_URL when proxy is disabled for this process."""
        monkeypatch.setenv("CHROME_PROXY_URL", "http://user:pass@proxy.example:33335")
        set_proxy_enabled(False)
        assert resolve_http_proxy() is None
        set_proxy_enabled(True)
        assert resolve_http_proxy() == "http://user:pass@proxy.example:33335"
