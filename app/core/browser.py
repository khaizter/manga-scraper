import asyncio
import logging
import os
from dataclasses import dataclass

from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.browser.tab import Tab
from pydoll.exceptions import FailedToStartBrowser, WaitElementTimeout

logger = logging.getLogger(__name__)

DEFAULT_START_TIMEOUT = 30
DEFAULT_START_RETRIES = 3
DEFAULT_START_RETRY_DELAY = 2.0
DEFAULT_CLOUDFLARE_WAIT = 45
DEFAULT_CLOUDFLARE_POST_CLICK_WAIT = 3.0
DEFAULT_PAGE_GUARD_WAIT = 60

CLOUDFLARE_CHALLENGE_DOMAIN = 'challenges.cloudflare.com'
CLOUDFLARE_IFRAME_SELECTOR = f'iframe[src*="{CLOUDFLARE_CHALLENGE_DOMAIN}"]'

DEFAULT_PAGE_GUARD_LOGO_SELECTOR = 'div.top-logo'
DEFAULT_PAGE_GUARD_LISTING_SELECTOR = 'div.comic-list div.list-comic-item-wrap'

# Obfuscated Turnstile classes (e.g. CDDrW6) rotate; prefer stable selectors.
# Override: CHROME_CLOUDFLARE_CHECKBOX_SELECTORS=input[type="checkbox"],label
DEFAULT_CLOUDFLARE_CHECKBOX_SELECTORS = (
    'input[type="checkbox"]',
    'span.cb-i',
    'label',
)


def get_chrome_options() -> ChromiumOptions:
    options = ChromiumOptions()

    chrome_bin = os.getenv('CHROME_BIN')
    if chrome_bin:
        options.binary_location = chrome_bin

    options.start_timeout = int(os.getenv('CHROME_START_TIMEOUT', DEFAULT_START_TIMEOUT))

    for arg in (
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-blink-features=AutomationControlled',
        '--window-size=1920,1080',
    ):
        options.add_argument(arg)

    if os.getenv('CHROME_HEADLESS', 'false').lower() == 'true':
        options.add_argument('--headless=new')

    return options


def _cloudflare_checkbox_selectors() -> tuple[str, ...]:
    raw = os.getenv('CHROME_CLOUDFLARE_CHECKBOX_SELECTORS')
    if not raw:
        return DEFAULT_CLOUDFLARE_CHECKBOX_SELECTORS
    return tuple(selector.strip() for selector in raw.split(',') if selector.strip())


def _page_guard_logo_selector() -> str:
    return os.getenv('CHROME_PAGE_GUARD_LOGO_SELECTOR', DEFAULT_PAGE_GUARD_LOGO_SELECTOR)


def _page_guard_listing_selector() -> str:
    return os.getenv('CHROME_PAGE_GUARD_LISTING_SELECTOR', DEFAULT_PAGE_GUARD_LISTING_SELECTOR)


@dataclass(frozen=True)
class PageGuardStatus:
    logo_present: bool
    listing_present: bool
    cloudflare_challenge_present: bool
    page_url: str


async def _selector_present(tab: Tab, selector: str, *, timeout: float = 0) -> bool:
    element = await tab.query(selector, timeout=timeout, raise_exc=False)
    return element is not None


async def _cloudflare_challenge_visible(tab: Tab) -> bool:
    try:
        await _find_cloudflare_shadow_root(tab, timeout=1)
        return True
    except WaitElementTimeout:
        return False


async def check_page_guard(tab: Tab) -> PageGuardStatus:
    """Check whether the real site chrome and listing markup are present."""
    logo_selector = _page_guard_logo_selector()
    listing_selector = _page_guard_listing_selector()
    query_timeout = 2

    return PageGuardStatus(
        logo_present=await _selector_present(tab, logo_selector, timeout=query_timeout),
        listing_present=await _selector_present(tab, listing_selector, timeout=query_timeout),
        cloudflare_challenge_present=await _cloudflare_challenge_visible(tab),
        page_url=await tab.current_url,
    )


def _log_page_guard(status: PageGuardStatus, *, level: int) -> None:
    passed = status.logo_present or status.listing_present
    message = (
        'Page guard: logo=%s (%s) listing=%s (%s) cloudflare_challenge=%s url=%s'
    )
    args = (
        status.logo_present,
        _page_guard_logo_selector(),
        status.listing_present,
        _page_guard_listing_selector(),
        status.cloudflare_challenge_present,
        status.page_url,
    )
    if passed:
        logger.log(level, 'Page guard passed — ' + message, *args)
    else:
        logger.log(level, 'Page guard failed — ' + message, *args)


async def wait_for_page_guard(tab: Tab, timeout: float | None = None) -> PageGuardStatus:
    """Wait until site logo or listing appears, or timeout."""
    wait_seconds = timeout if timeout is not None else float(
        os.getenv('CHROME_PAGE_GUARD_WAIT', DEFAULT_PAGE_GUARD_WAIT),
    )
    deadline = asyncio.get_event_loop().time() + wait_seconds
    last_status = await check_page_guard(tab)

    while asyncio.get_event_loop().time() < deadline:
        if last_status.logo_present or last_status.listing_present:
            _log_page_guard(last_status, level=logging.INFO)
            return last_status
        await asyncio.sleep(0.5)
        last_status = await check_page_guard(tab)

    _log_page_guard(last_status, level=logging.WARNING)
    return last_status


async def start_tab(browser: Chrome) -> Tab:
    """Start Chrome with retries for slow or cold Docker startups."""
    retries = int(os.getenv('CHROME_START_RETRIES', DEFAULT_START_RETRIES))
    retry_delay = float(os.getenv('CHROME_START_RETRY_DELAY', DEFAULT_START_RETRY_DELAY))
    last_error: FailedToStartBrowser | None = None

    for attempt in range(1, retries + 1):
        try:
            return await browser.start()
        except FailedToStartBrowser as exc:
            last_error = exc
            if attempt < retries:
                await asyncio.sleep(retry_delay * attempt)

    raise last_error or FailedToStartBrowser()


async def _find_cloudflare_shadow_root(tab: Tab, timeout: float):
    """Poll until a shadow root containing the Cloudflare challenge iframe appears."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        for shadow_root in await tab.find_shadow_roots(deep=False):
            html = await shadow_root.inner_html
            if CLOUDFLARE_CHALLENGE_DOMAIN in html:
                return shadow_root
        await asyncio.sleep(0.5)

    raise WaitElementTimeout(
        f'Timed out after {timeout}s waiting for Cloudflare Turnstile shadow root',
    )


async def bypass_cloudflare_turnstile(tab: Tab, timeout: float | None = None) -> bool:
    """
    Click the Turnstile checkbox inside Cloudflare's nested shadow DOM.

    Returns True when a checkbox was clicked, False when no challenge was found.
    """
    wait_seconds = timeout if timeout is not None else float(
        os.getenv('CHROME_CLOUDFLARE_WAIT', DEFAULT_CLOUDFLARE_WAIT),
    )
    query_timeout = max(1, min(15, int(wait_seconds)))

    try:
        shadow_root = await _find_cloudflare_shadow_root(tab, wait_seconds)
    except WaitElementTimeout:
        return False

    try:
        iframe = await shadow_root.query(CLOUDFLARE_IFRAME_SELECTOR, timeout=query_timeout)
        body = await iframe.find(tag_name='body', timeout=query_timeout)
        inner_shadow = await body.get_shadow_root(timeout=wait_seconds)

        for selector in _cloudflare_checkbox_selectors():
            try:
                target = await inner_shadow.query(selector, timeout=query_timeout)
                await target.click()
                logger.info('Clicked Cloudflare Turnstile checkbox via %s', selector)

                post_click_wait = float(
                    os.getenv('CHROME_CLOUDFLARE_POST_CLICK_WAIT', DEFAULT_CLOUDFLARE_POST_CLICK_WAIT),
                )
                if post_click_wait > 0:
                    await asyncio.sleep(post_click_wait)
                return True
            except WaitElementTimeout:
                logger.debug('Cloudflare selector not found: %s', selector)
            except Exception as exc:
                logger.debug('Cloudflare selector %s failed: %s', selector, exc)

        logger.error(
            'Cloudflare Turnstile found but no checkbox matched: %s',
            ', '.join(_cloudflare_checkbox_selectors()),
        )
    except Exception as exc:
        logger.error('Error bypassing Cloudflare Turnstile: %s', exc)

    return False


async def navigate_to(tab: Tab, url: str) -> None:
    """Navigate, bypass Turnstile when present, then wait for site page guard."""
    await tab.go_to(url)
    clicked = await bypass_cloudflare_turnstile(tab)
    if clicked:
        logger.info('Cloudflare checkbox clicked; waiting for site content to load')
    status = await wait_for_page_guard(tab)
    if not status.logo_present and not status.listing_present:
        logger.warning(
            'Site content not detected after navigation — possible Cloudflare block, '
            'slow verification, or datacenter IP rejection',
        )
