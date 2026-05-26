import asyncio
import os

from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions
from pydoll.browser.tab import Tab
from pydoll.exceptions import FailedToStartBrowser

DEFAULT_START_TIMEOUT = 30
DEFAULT_START_RETRIES = 3
DEFAULT_START_RETRY_DELAY = 2.0


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
        '--window-size=1920,1080',
    ):
        options.add_argument(arg)

    if os.getenv('CHROME_HEADLESS', 'false').lower() == 'true':
        options.add_argument('--headless=new')

    return options


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


async def navigate_to(tab: Tab, url: str) -> None:
    """Navigate with Cloudflare Turnstile bypass enabled."""
    await tab.enable_auto_solve_cloudflare_captcha()
    try:
        async with tab.expect_and_bypass_cloudflare_captcha(time_to_wait_captcha=30):
            await tab.go_to(url)
    finally:
        await tab.disable_auto_solve_cloudflare_captcha()
