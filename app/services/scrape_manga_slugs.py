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
TITLE_LINK_SELECTOR = 'h3 > a'
DESCRIPTION_SELECTOR = 'p'
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
        selector=TITLE_LINK_SELECTOR,
        description='Manga title',
    )
    slug: str = Field(
        selector=TITLE_LINK_SELECTOR,
        attribute='href',
        description='Manga slug from detail page URL',
        transform=extract_slug,
    )
    description: Optional[str] = Field(
        selector=DESCRIPTION_SELECTOR,
        description='Manga synopsis',
        default=None,
    )


async def extract_list_item_from_container(container) -> MangaListItem:
    """Extract a MangaListItem from an already-located list-item container."""
    title_el = await container.query(TITLE_LINK_SELECTOR, timeout=SCRAPE_TIMEOUT, raise_exc=True)
    title = await title_el.text
    href = title_el.get_attribute('href') or ''
    slug = extract_slug(href)

    desc_el = await container.query(DESCRIPTION_SELECTOR, timeout=SCRAPE_TIMEOUT, raise_exc=False)
    description = await desc_el.text if desc_el else None

    return MangaListItem(title=title, slug=slug, description=description)


async def process_list_item(container) -> dict[str, Any]:
    item = await extract_list_item_from_container(container)
    # Query the img separately so fetch_image_data_uri_from_element can fall back
    # to JS `return this.src` when src/data-src are not available yet (lazy load).
    img = await container.query(COVER_IMAGE_SELECTOR, raise_exc=False)
    if not img:
        return {**item.model_dump(), 'imageDataUri': ''}
    image_data_uri = await fetch_image_data_uri_from_element(img) or ''
    return {**item.model_dump(), 'imageDataUri': image_data_uri}


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
        containers = await tab.query(
            LIST_ITEM_SCOPE,
            find_all=True,
            timeout=SCRAPE_TIMEOUT,
            raise_exc=False,
        )

        if not containers:
            return {'items': [], 'totalPages': total_pages}

        items = await asyncio.gather(
            *[process_list_item(container) for container in containers]
        )

        return {'items': list(items), 'totalPages': total_pages}
