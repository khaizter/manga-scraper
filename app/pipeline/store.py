import asyncio
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.firebase import get_firestore_client
from app.pipeline.config import PIPELINE_STATE_DIR
from app.pipeline.models import ChapterDocument, MangaDocument, utcnow

MANGAS_COLLECTION = 'mangas'
CHAPTERS_SUBCOLLECTION = 'chapters'


class MangaStore(ABC):
    @abstractmethod
    async def upsert_manga(self, manga: MangaDocument) -> None:
        pass

    @abstractmethod
    async def upsert_chapter(self, manga_slug: str, chapter: ChapterDocument) -> None:
        pass

    @abstractmethod
    async def get_manga(self, slug: str) -> MangaDocument | None:
        pass


class JsonFileStore(MangaStore):
    """Local file store for pipeline testing. Mirrors Firestore document shape."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or (PIPELINE_STATE_DIR / 'mangas')
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _manga_path(self, slug: str) -> Path:
        return self.data_dir / slug / 'manga.json'

    def _chapters_path(self, slug: str) -> Path:
        return self.data_dir / slug / 'chapters.json'

    async def upsert_manga(self, manga: MangaDocument) -> None:
        path = self._manga_path(manga.slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        manga.updated_at = utcnow()
        path.write_text(
            manga.model_dump_json(indent=2),
            encoding='utf-8',
        )

    async def upsert_chapter(self, manga_slug: str, chapter: ChapterDocument) -> None:
        path = self._chapters_path(manga_slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        chapters: dict[str, dict] = {}
        if path.exists():
            chapters = json.loads(path.read_text(encoding='utf-8'))
        chapters[chapter.chapter_number] = chapter.model_dump(mode='json')
        path.write_text(
            json.dumps(chapters, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )

    async def get_manga(self, slug: str) -> MangaDocument | None:
        path = self._manga_path(slug)
        if not path.exists():
            return None
        return MangaDocument.model_validate_json(path.read_text(encoding='utf-8'))


class FirestoreStore(MangaStore):
    """Firestore-backed store for pipeline sync."""

    def __init__(self) -> None:
        self._db = get_firestore_client()

    def _upsert_manga_sync(self, manga: MangaDocument) -> None:
        manga.updated_at = utcnow()
        payload = manga.model_dump(mode='json')
        self._db.collection(MANGAS_COLLECTION).document(manga.slug).set(payload, merge=True)

    def _upsert_chapter_sync(self, manga_slug: str, chapter: ChapterDocument) -> None:
        payload = chapter.model_dump(mode='json')
        self._db.collection(MANGAS_COLLECTION).document(manga_slug).collection(
            CHAPTERS_SUBCOLLECTION,
        ).document(chapter.chapter_number).set(payload, merge=True)

    def _get_manga_sync(self, slug: str) -> MangaDocument | None:
        snapshot = self._db.collection(MANGAS_COLLECTION).document(slug).get()
        if not snapshot.exists:
            return None
        return MangaDocument.model_validate(snapshot.to_dict())

    async def upsert_manga(self, manga: MangaDocument) -> None:
        await asyncio.to_thread(self._upsert_manga_sync, manga)

    async def upsert_chapter(self, manga_slug: str, chapter: ChapterDocument) -> None:
        await asyncio.to_thread(self._upsert_chapter_sync, manga_slug, chapter)

    async def get_manga(self, slug: str) -> MangaDocument | None:
        return await asyncio.to_thread(self._get_manga_sync, slug)


def get_manga_store() -> MangaStore:
    store_type = os.getenv('PIPELINE_STORE', 'json').lower()
    if store_type == 'firestore':
        return FirestoreStore()
    return JsonFileStore()
