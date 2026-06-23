import asyncio
import base64
from urllib.parse import urljoin, urlparse

from pydoll.browser.tab import Tab
from pydoll.elements.web_element import WebElement

from app.core.config import BASE_URL
from app.core.http_client import http_session, resolve_http_proxy

IMAGE_MIME_TYPES = {
    '.webp': 'image/webp',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
}

DEFAULT_HEADERS = {
    'Referer': f'{BASE_URL}/',
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
}


def normalize_image_url(url: str, base_url: str = BASE_URL) -> str:
    if url.startswith('//'):
        return f'https:{url}'
    if url.startswith('/'):
        return urljoin(base_url, url)
    return url


def image_mime_type(url: str) -> str:
    path = urlparse(url).path.lower()
    for ext, mime in IMAGE_MIME_TYPES.items():
        if path.endswith(ext):
            return mime
    return 'image/jpeg'


def build_image_data_uri(image_base64: str, url: str) -> str:
    mime = image_mime_type(url)
    return f'data:{mime};base64,{image_base64}'


async def fetch_image_base64(url: str) -> str:
    async with http_session(DEFAULT_HEADERS) as session:
        async with session.get(url, proxy=resolve_http_proxy()) as response:
            response.raise_for_status()
            return base64.b64encode(await response.read()).decode('ascii')


async def get_image_url(img: WebElement) -> str:
    image_url = img.get_attribute('src') or img.get_attribute('data-src') or ''

    # Fallback: Pydoll may not cache src; read the live URL from the browser DOM.
    if not image_url:
        response = await img.execute_script('return this.src', return_by_value=True)
        image_url = response.get('result', {}).get('result', {}).get('value', '') or ''

    return normalize_image_url(image_url) if image_url else ''


async def fetch_image_data_uri(url: str) -> str:
    image = await fetch_image_base64(url)
    return build_image_data_uri(image, url)


async def fetch_image_data_uri_from_element(img: WebElement) -> str | None:
    url = await get_image_url(img)
    if not url:
        return None
    return await fetch_image_data_uri(url)


async def fetch_image_data_uris_from_selector(tab: Tab, selector: str, *, timeout: int = 30) -> list[str]:
    imgs = await tab.query(selector, find_all=True, timeout=timeout, raise_exc=False)
    if not imgs:
        return []

    urls: list[str] = []
    for img in imgs:
        url = await get_image_url(img)
        if url:
            urls.append(url)

    if not urls:
        return []

    return list(await asyncio.gather(*[fetch_image_data_uri(url) for url in urls]))
