import asyncio
import logging
import os

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

CLOUDFLARE_CHALLENGE_DOMAIN = 'challenges.cloudflare.com'
CLOUDFLARE_IFRAME_SELECTOR = f'iframe[src*="{CLOUDFLARE_CHALLENGE_DOMAIN}"]'

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
    """Navigate and attempt to click Cloudflare Turnstile when present."""
    await tab.go_to(url)
    await bypass_cloudflare_turnstile(tab)
