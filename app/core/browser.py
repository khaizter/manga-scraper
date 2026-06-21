import asyncio
import logging
import os
from dataclasses import dataclass
from urllib.parse import urlparse

from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.browser.tab import Tab
from pydoll.commands.page_commands import PageCommands
from pydoll.constants import PageLoadState
from pydoll.exceptions import (
    FailedToStartBrowser,
    NavigationError,
    ShadowRootNotFound,
    WaitElementTimeout,
)

from app.core.proxy_ca import configure_chrome_proxy_ssl

logger = logging.getLogger(__name__)

DEFAULT_START_TIMEOUT = 30
DEFAULT_START_RETRIES = 3
DEFAULT_START_RETRY_DELAY = 2.0
DEFAULT_CLOUDFLARE_WAIT = 45
DEFAULT_CLOUDFLARE_POST_CLICK_WAIT = 3.0
DEFAULT_CLOUDFLARE_RENDER_WAIT = 3.0
DEFAULT_CLOUDFLARE_RETRIES = 3
DEFAULT_PAGE_GUARD_WAIT = 60
DEFAULT_NAVIGATE_TIMEOUT = 300

DEFAULT_PROXY_WARMUP_URL = 'https://geo.brdtest.com/welcome.txt?product=isp&method=native'

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


def _proxy_log_label(proxy_url: str) -> str:
    parsed = urlparse(proxy_url)
    if parsed.hostname:
        return f'{parsed.hostname}:{parsed.port}' if parsed.port else parsed.hostname
    return 'configured'


def _resolve_proxy_server_url() -> str | None:
    """
    Build --proxy-server URL for Chrome from CHROME_PROXY_URL.

    Example: http://user:pass@proxy-host:6754

    When unset, returns None and Chrome connects directly.
    """
    proxy_url = os.getenv('CHROME_PROXY_URL', '').strip()
    if not proxy_url:
        return None
    if '://' not in proxy_url:
        proxy_url = f'http://{proxy_url}'
    return proxy_url


def _navigate_timeout() -> int:
    return int(os.getenv('CHROME_NAVIGATE_TIMEOUT', DEFAULT_NAVIGATE_TIMEOUT))


async def _go_to(tab: Tab, url: str, timeout: int | None = None) -> None:
    """
    Navigate and wait for page load.

    pydoll's tab.go_to() passes timeout only to the load-event wait; Tab._execute_command
    always uses a 60s CDP timeout. Proxy + Cloud Run can exceed that, so we call the
    connection handler directly with a longer timeout.
    """
    wait_seconds = timeout if timeout is not None else _navigate_timeout()
    logger.info('Navigating to URL: %s (timeout=%ss)', url, wait_seconds)
    command = PageCommands.navigate(url)
    handler, session_id = tab._resolve_routing()
    if session_id:
        command['sessionId'] = session_id
    async with tab._wait_page_load(timeout=wait_seconds):
        response = await handler.execute_command(command, timeout=wait_seconds)
        error_text = response['result'].get('errorText')
        if error_text:
            raise NavigationError(url, error_text)
    logger.info('Navigation complete: %s', url)


async def _warm_up_proxy(tab: Tab) -> None:
    """
    First navigation triggers pydoll's browser-level Fetch proxy auth.

    Do not enable tab-level Fetch — it conflicts with browser-level proxy auth.
    """
    warmup_url = os.getenv('CHROME_PROXY_WARMUP_URL', DEFAULT_PROXY_WARMUP_URL).strip()
    logger.info('Warming up proxy via browser-level auth (%s)', warmup_url)
    try:
        await _go_to(tab, warmup_url, timeout=min(_navigate_timeout(), 90))
        logger.info('Proxy warm-up complete')
    except Exception as exc:
        logger.warning('Proxy warm-up failed (continuing anyway): %s', exc)


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

    proxy_url = _resolve_proxy_server_url()
    if proxy_url:
        options.add_argument(f'--proxy-server={proxy_url}')
        options.page_load_state = PageLoadState.INTERACTIVE
        configure_chrome_proxy_ssl(options)
        logger.info('Using Chrome proxy %s', _proxy_log_label(proxy_url))

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
    last_bypass_at = 0.0
    bypass_interval = 10.0

    while asyncio.get_event_loop().time() < deadline:
        if last_status.logo_present or last_status.listing_present:
            _log_page_guard(last_status, level=logging.INFO)
            return last_status

        now = asyncio.get_event_loop().time()
        if last_status.cloudflare_challenge_present and now - last_bypass_at >= bypass_interval:
            logger.info('Cloudflare still present during page guard wait; retrying bypass')
            await bypass_cloudflare_turnstile(tab)
            last_bypass_at = now

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
            tab = await browser.start()
            if _resolve_proxy_server_url():
                await _warm_up_proxy(tab)
            return tab
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


async def _poll_body_shadow_root(body, timeout: float):
    """Poll until Turnstile attaches its inner shadow root to the iframe body."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            return await body.get_shadow_root(timeout=0)
        except (ShadowRootNotFound, WaitElementTimeout):
            await asyncio.sleep(0.5)

    raise WaitElementTimeout(
        f'Timed out after {timeout}s waiting for shadow root on element',
    )


async def _cloudflare_post_click_wait() -> None:
    post_click_wait = float(
        os.getenv('CHROME_CLOUDFLARE_POST_CLICK_WAIT', DEFAULT_CLOUDFLARE_POST_CLICK_WAIT),
    )
    if post_click_wait > 0:
        await asyncio.sleep(post_click_wait)


async def _try_click_turnstile(container, selectors: tuple[str, ...], *, humanize: bool = True) -> bool:
    for selector in selectors:
        try:
            target = await container.query(selector, timeout=3)
            await target.click(humanize=humanize)
            logger.info('Clicked Cloudflare Turnstile via %s', selector)
            return True
        except WaitElementTimeout:
            logger.debug('Cloudflare selector not found: %s', selector)
        except Exception as exc:
            logger.debug('Cloudflare selector %s failed: %s', selector, exc)
    return False


async def _click_turnstile_iframe(iframe) -> bool:
    try:
        await iframe.click(humanize=True)
        logger.info('Clicked Cloudflare Turnstile iframe (fallback)')
        return True
    except Exception as exc:
        logger.warning('Turnstile iframe click fallback failed: %s', exc)
        return False


async def bypass_cloudflare_turnstile(tab: Tab, timeout: float | None = None) -> bool:
    """
    Click the Turnstile checkbox inside Cloudflare's nested shadow DOM.

    Returns True when a click was attempted, False when no challenge was found.
    """
    wait_seconds = timeout if timeout is not None else float(
        os.getenv('CHROME_CLOUDFLARE_WAIT', DEFAULT_CLOUDFLARE_WAIT),
    )
    render_wait = float(os.getenv('CHROME_CLOUDFLARE_RENDER_WAIT', DEFAULT_CLOUDFLARE_RENDER_WAIT))
    retries = int(os.getenv('CHROME_CLOUDFLARE_RETRIES', DEFAULT_CLOUDFLARE_RETRIES))
    selectors = _cloudflare_checkbox_selectors()

    for attempt in range(1, retries + 1):
        try:
            shadow_root = await _find_cloudflare_shadow_root(tab, min(15, wait_seconds))
        except WaitElementTimeout:
            if attempt == 1:
                logger.info('No Cloudflare Turnstile challenge detected')
            return False

        logger.info(
            'Cloudflare Turnstile challenge detected; bypass attempt %s/%s',
            attempt,
            retries,
        )

        if await _try_click_turnstile(shadow_root, selectors):
            await _cloudflare_post_click_wait()
            return True

        iframe = None
        try:
            iframe = await shadow_root.query(CLOUDFLARE_IFRAME_SELECTOR, timeout=10)
            await asyncio.sleep(render_wait)

            body = await iframe.find(tag_name='body', timeout=10)
            inner_shadow = await _poll_body_shadow_root(body, wait_seconds)

            if await _try_click_turnstile(inner_shadow, selectors):
                await _cloudflare_post_click_wait()
                return True
        except WaitElementTimeout:
            logger.warning(
                'Turnstile inner shadow not ready on attempt %s/%s; trying iframe click',
                attempt,
                retries,
            )
        except Exception as exc:
            logger.error('Error bypassing Cloudflare Turnstile: %s', exc)

        if iframe is None:
            try:
                iframe = await shadow_root.query(CLOUDFLARE_IFRAME_SELECTOR, timeout=5)
            except WaitElementTimeout:
                iframe = None

        if iframe and await _click_turnstile_iframe(iframe):
            await _cloudflare_post_click_wait()
            return True

        if attempt < retries:
            await asyncio.sleep(2)

    logger.error(
        'Cloudflare Turnstile found but bypass failed after %s attempts',
        retries,
    )
    return False


async def navigate_to(tab: Tab, url: str) -> None:
    """Navigate, bypass Turnstile when present, then wait for site page guard."""
    await _go_to(tab, url)
    clicked = await bypass_cloudflare_turnstile(tab)
    if clicked:
        logger.info('Cloudflare checkbox clicked; waiting for site content to load')
    status = await wait_for_page_guard(tab)
    if not status.logo_present and not status.listing_present:
        logger.warning(
            'Site content not detected after navigation — possible Cloudflare block, '
            'slow verification, or datacenter IP rejection',
        )
