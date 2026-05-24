import base64
from typing import Any
from urllib.parse import urljoin, urlparse

import aiohttp
from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.browser.tab import Tab
from pydoll.extractor import ExtractionModel, Field

BASE_URL = 'https://www.mangakakalot.gg'
COVER_IMAGE_SELECTOR = 'div.manga-info-pic img'

IMAGE_MIME_TYPES = {
    '.webp': 'image/webp',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
}


def strip_label_value(text: str) -> str:
    if ':' in text:
        return text.split(':', 1)[1].strip()
    return text.strip()


def chapter_to_slug(text: str) -> str:
    return text.strip().lower().replace('.', '-').replace(' ', '-')


class MangaDetail(ExtractionModel):
    author: str = Field(
        selector='ul.manga-info-text li:nth-child(2)',
        description='Manga author',
        transform=strip_label_value,
    )
    status: str = Field(
        selector='ul.manga-info-text li:nth-child(3)',
        description='Manga status',
        transform=strip_label_value,
    )
    chapters: list[str] = Field(
        selector='div.chapter-list div.row span a',
        description='Chapter slugs',
        transform=chapter_to_slug,
    )


async def fetch_image_base64(url: str) -> str:
    headers = {
        'Referer': f'{BASE_URL}/',
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ),
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            return base64.b64encode(await response.read()).decode('ascii')


def image_mime_type(url: str) -> str:
    path = urlparse(url).path.lower()
    for ext, mime in IMAGE_MIME_TYPES.items():
        if path.endswith(ext):
            return mime
    return 'image/jpeg'


async def get_cover_image(tab: Tab) -> dict[str, str]:
    img = await tab.query(COVER_IMAGE_SELECTOR, timeout=30)
    image_url = img.get_attribute('src') or ''

    # Fallback: Pydoll may not cache src; read the live URL from the browser DOM.
    if not image_url:
        response = await img.execute_script('return this.src', return_by_value=True)
        image_url = response.get('result', {}).get('result', {}).get('value', '') or ''

    if not image_url:
        return {'image': '', 'imageDataUri': ''}

    # Normalize relative URLs so aiohttp can download the image.
    if image_url.startswith('//'):
        image_url = f'https:{image_url}'
    elif image_url.startswith('/'):
        image_url = urljoin(BASE_URL, image_url)

    image = await fetch_image_base64(image_url)
    mime = image_mime_type(image_url)

    return {
        'image': image, # Base64 encoded image data
        'imageDataUri': f'data:{mime};base64,{image}', # Data URI for inline display
    }


async def scrape_manga(slug: str) -> dict[str, Any]:
    options = ChromiumOptions()

    async with Chrome(options=options) as browser:
        tab = await browser.start()
        await tab.go_to(f'{BASE_URL}/manga/{slug}')
        detail = await tab.extract(MangaDetail, timeout=30)
        cover = await get_cover_image(tab)

    return {
        **detail.model_dump(),
        **cover,
    }
