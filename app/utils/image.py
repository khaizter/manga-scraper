import base64
from urllib.parse import urljoin, urlparse

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
    """Resolve protocol-relative and site-relative image URLs to absolute HTTPS."""
    if url.startswith('//'):
        return f'https:{url}'
    if url.startswith('/'):
        return urljoin(base_url, url)
    return url


def image_mime_type(url: str) -> str:
    """Infer MIME type from the image URL file extension."""
    path = urlparse(url).path.lower()
    for ext, mime in IMAGE_MIME_TYPES.items():
        if path.endswith(ext):
            return mime
    return 'image/jpeg'


def build_image_data_uri(image_base64: str, url: str) -> str:
    """Wrap base64 image bytes in a data: URI."""
    mime = image_mime_type(url)
    return f'data:{mime};base64,{image_base64}'


async def fetch_image_base64(url: str) -> str:
    """Download image bytes over HTTP and return base64-encoded ASCII."""
    async with http_session(DEFAULT_HEADERS) as session:
        async with session.get(url, proxy=resolve_http_proxy()) as response:
            response.raise_for_status()
            return base64.b64encode(await response.read()).decode('ascii')


async def get_image_url(img: WebElement) -> str:
    """Read src/data-src on an img element, or run JS `return this.src` as fallback."""
    image_url = img.get_attribute('src') or img.get_attribute('data-src') or ''

    # Pydoll may not cache src; read the live URL from the browser DOM.
    if not image_url:
        response = await img.execute_script('return this.src', return_by_value=True)
        image_url = response.get('result', {}).get('result', {}).get('value', '') or ''

    return image_url


async def fetch_image_data_uri_from_element(img: WebElement) -> str | None:
    """Resolve an img element's URL and return its image as a data: URI."""
    url = await get_image_url(img)
    if not url:
        return None
    normalized_image_url = normalize_image_url(url)
    image_base64 = await fetch_image_base64(normalized_image_url)
    image_data_uri = build_image_data_uri(image_base64, normalized_image_url)
    return image_data_uri
