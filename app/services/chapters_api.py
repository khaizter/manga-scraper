import aiohttp

from app.core.config import CHAPTERS_API_URL
from app.utils.image import DEFAULT_HEADERS

CHAPTER_SLUG_PREFIX = 'chapter-'


def to_chapter_number(chapter_slug: str) -> str:
    if chapter_slug.startswith(CHAPTER_SLUG_PREFIX):
        return chapter_slug[len(CHAPTER_SLUG_PREFIX):]
    return chapter_slug


async def fetch_chapter_numbers(manga_slug: str) -> list[str]:
    url = CHAPTERS_API_URL.format(slug=manga_slug)

    async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            payload = await response.json()

    if not payload.get('success'):
        return []

    chapters = payload.get('data', {}).get('chapters', [])
    return [
        to_chapter_number(chapter['chapter_slug'])
        for chapter in chapters
        if chapter.get('chapter_slug')
    ]
