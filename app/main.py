from fastapi import FastAPI

from app.api.router import api_router

app = FastAPI(
    title='Manga Scraper API',
    description='Scrape manga data from mangakakalot.gg',
    version='1.0.0',
)

app.include_router(api_router)


@app.get('/health')
async def health_check() -> dict[str, str]:
    return {'status': 'ok'}
