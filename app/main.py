from typing import Any

from app.core.env import load_env

load_env()

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydoll.exceptions import FailedToStartBrowser, WaitElementTimeout

from app.api.router import api_router
from app.core.display import check_virtual_display

app = FastAPI(
    title='Manga Scraper API',
    description='Scrape manga data from mangakakalot.gg',
    version='1.0.0',
)

app.include_router(api_router)


@app.exception_handler(FailedToStartBrowser)
async def browser_start_handler(_request: Request, exc: FailedToStartBrowser) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            'detail': (
                'Browser failed to start. The virtual display may not be ready yet — '
                'try restarting the container with: docker compose restart api'
            ),
            'error': str(exc),
        },
    )


@app.exception_handler(WaitElementTimeout)
async def scrape_timeout_handler(_request: Request, exc: WaitElementTimeout) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            'detail': (
                'Scrape timed out waiting for page content. '
                'The site may be blocking automated access.'
            ),
            'error': str(exc),
        },
    )


@app.get('/health', response_model=None)
async def health_check():
    display = await check_virtual_display()
    display_ready = display['ready'] is True
    display_required = display['configured']
    healthy = not display_required or display_ready

    body: dict[str, Any] = {
        'status': 'ok' if healthy else 'unhealthy',
        'display': display,
    }

    if not healthy:
        return JSONResponse(status_code=503, content=body)

    return body
