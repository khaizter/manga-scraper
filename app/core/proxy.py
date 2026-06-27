import os

_proxy_disabled = False


def set_proxy_enabled(enabled: bool) -> None:
    """Enable or disable proxy usage for this process (e.g. CLI --non-proxy)."""
    global _proxy_disabled
    _proxy_disabled = not enabled


def is_proxy_enabled() -> bool:
    if _proxy_disabled:
        return False
    return bool(os.getenv('CHROME_PROXY_URL', '').strip())


def resolve_proxy_url() -> str | None:
    """Return CHROME_PROXY_URL when proxy is enabled, else None."""
    if not is_proxy_enabled():
        return None

    proxy_url = os.getenv('CHROME_PROXY_URL', '').strip()
    if '://' not in proxy_url:
        proxy_url = f'http://{proxy_url}'
    return proxy_url
