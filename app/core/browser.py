import os

from pydoll.browser.options import ChromiumOptions
from pydoll.browser.tab import Tab


def get_chrome_options() -> ChromiumOptions:
    options = ChromiumOptions()

    chrome_bin = os.getenv('CHROME_BIN')
    if chrome_bin:
        options.binary_location = chrome_bin

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


async def navigate_to(tab: Tab, url: str) -> None:
    """Navigate with Cloudflare Turnstile bypass enabled."""
    await tab.enable_auto_solve_cloudflare_captcha()
    try:
        async with tab.expect_and_bypass_cloudflare_captcha(time_to_wait_captcha=30):
            await tab.go_to(url)
    finally:
        await tab.disable_auto_solve_cloudflare_captcha()
