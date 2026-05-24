import os

from pydoll.browser.options import ChromiumOptions


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
