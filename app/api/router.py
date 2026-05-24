from fastapi import APIRouter

from app.api.routes import manga

api_router = APIRouter()
api_router.include_router(manga.router)
