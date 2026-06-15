import asyncio
import logging
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from pydoll.browser.chromium import Chrome
from pydoll.browser.tab import Tab
from pydoll.extractor import ExtractionModel, Field

from app.core.browser import get_chrome_options, navigate_to, start_tab
from app.core.config import LIST_URL, SCRAPE_TIMEOUT
from app.utils.image import fetch_image_data_uri_from_element

logger = logging.getLogger(__name__)

LIST_ITEM_SCOPE = 'div.comic-list div.list-comic-item-wrap'
COVER_IMAGE_SELECTOR = 'a.cover > img'
PAGINATION_SELECTOR = 'div.group_page > a'


def extract_slug(url: str) -> str:
    path = urlparse(url).path.rstrip('/')
    prefix = '/manga/'
    if path.startswith(prefix):
        return path[len(prefix):]
    return path.split('/')[-1]


def extract_page_from_href(href: str) -> int | None:
    page_values = parse_qs(urlparse(href).query).get('page', [])
    if not page_values:
        return None
    try:
        return int(page_values[0])
    except ValueError:
        return None


class MangaListItem(ExtractionModel):
    title: str = Field(
        selector='h3 > a',
        description='Manga title',
    )
    slug: str = Field(
        selector='h3 > a',
        attribute='href',
        description='Manga slug from detail page URL',
        transform=extract_slug,
    )
    description: Optional[str] = Field(
        selector='p',
        description='Manga synopsis',
        default=None,
    )


async def get_list_item_image_data_uri(container) -> str:
    img = await container.query(COVER_IMAGE_SELECTOR, raise_exc=False)
    if not img:
        return ''
    return await fetch_image_data_uri_from_element(img) or ''


async def get_total_pages(tab: Tab) -> int | None:
    links = await tab.query(
        PAGINATION_SELECTOR,
        find_all=True,
        timeout=SCRAPE_TIMEOUT,
        raise_exc=False,
    )
    if not links:
        return None

    max_page = 0
    for link in links:
        href = link.get_attribute('href') or ''
        if not href:
            response = await link.execute_script('return this.href', return_by_value=True)
            href = response.get('result', {}).get('result', {}).get('value', '') or ''

        page = extract_page_from_href(href)
        if page and page > max_page:
            max_page = page

    return max_page if max_page > 0 else None


async def scrape_list_page_slugs(tab: Tab) -> list[str]:
    items = await tab.extract_all(
        MangaListItem,
        scope=LIST_ITEM_SCOPE,
        timeout=SCRAPE_TIMEOUT,
    )
    return [item.slug for item in items]


async def get_manga_list(page: int = 1) -> dict[str, Any]:
    options = get_chrome_options()

    async with Chrome(options=options) as browser:
        tab = await start_tab(browser)
        await navigate_to(tab, f'{LIST_URL}?page={page}')
        total_pages = await get_total_pages(tab)
        items = await tab.extract_all(
            MangaListItem,
            scope=LIST_ITEM_SCOPE,
            timeout=SCRAPE_TIMEOUT,
        )

        if not items:
            return {'items': [], 'totalPages': total_pages}

        containers = await tab.query(
            LIST_ITEM_SCOPE,
            find_all=True,
            timeout=SCRAPE_TIMEOUT,
            raise_exc=False,
        )

        if not containers:
            return {
                'items': [{**item.model_dump(), 'imageDataUri': ''} for item in items],
                'totalPages': total_pages,
            }

        image_data_uris = await asyncio.gather(
            *[get_list_item_image_data_uri(container) for container in containers]
        )

        return {
            'items': [
                {**item.model_dump(), 'imageDataUri': image_data_uri}
                for item, image_data_uri in zip(items, image_data_uris)
            ],
            'totalPages': total_pages,
        }
