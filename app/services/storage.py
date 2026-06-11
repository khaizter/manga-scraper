import asyncio
import base64
import logging
import re

from app.core.firebase import get_storage_bucket
from app.pipeline.models import manga_cover_storage_path

logger = logging.getLogger(__name__)

DATA_URI_PATTERN = re.compile(r'^data:(?P<mime>[^;]+);base64,(?P<data>.+)$')

MIME_EXTENSIONS = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp',
    'image/gif': 'gif',
}


def parse_data_uri(data_uri: str) -> tuple[str, bytes]:
    match = DATA_URI_PATTERN.match(data_uri.strip())
    if not match:
        raise ValueError('Invalid image data URI')

    mime = match.group('mime')
    data = base64.b64decode(match.group('data'))
    return mime, data


def _upload_bytes_sync(storage_path: str, data: bytes, content_type: str) -> None:
    bucket = get_storage_bucket()
    blob = bucket.blob(storage_path)
    blob.upload_from_string(data, content_type=content_type)


async def upload_manga_cover(slug: str, data_uri: str) -> str:
    """Upload a cover image and return its Storage object path."""
    mime, data = parse_data_uri(data_uri)
    extension = MIME_EXTENSIONS.get(mime, 'jpg')
    storage_path = manga_cover_storage_path(slug, extension)
    await asyncio.to_thread(_upload_bytes_sync, storage_path, data, mime)
    logger.info('Uploaded cover for %s to %s', slug, storage_path)
    return storage_path
