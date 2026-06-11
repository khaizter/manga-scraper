import asyncio
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.firebase import get_firestore_client
from app.pipeline.chapter_selection import select_pending_chapters
from app.pipeline.config import PIPELINE_MAX_RETRIES, PIPELINE_STATE_DIR
from app.pipeline.models import ChapterDocument, MangaDocument, PendingChapter, ScrapeStatus, utcnow

MANGAS_COLLECTION = 'mangas'
CHAPTERS_SUBCOLLECTION = 'chapters'
SYNCABLE_STATUSES = (
    ScrapeStatus.PROCESSING,
    ScrapeStatus.PENDING,
    ScrapeStatus.FAILED,
)


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

    @abstractmethod
    async def enqueue_slugs(self, slugs: list[str]) -> int:
        pass

    @abstractmethod
    async def get_pending_mangas(self, limit: int) -> list[MangaDocument]:
        pass

    @abstractmethod
    async def count_scrape_status(self) -> dict[str, int]:
        pass

    @abstractmethod
    async def get_pending_chapters(self, limit: int) -> list[PendingChapter]:
        pass

    @abstractmethod
    async def count_pending_chapters(self) -> int:
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

    def _list_manga_slugs(self) -> list[str]:
        return [
            path.name
            for path in self.data_dir.iterdir()
            if path.is_dir() and self._manga_path(path.name).exists()
        ]

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

    async def enqueue_slugs(self, slugs: list[str]) -> int:
        added = 0
        for slug in slugs:
            existing = await self.get_manga(slug)
            if existing and existing.scrape_status != ScrapeStatus.FAILED:
                continue
            stub = MangaDocument.pending_stub(slug)
            if existing:
                stub.created_at = existing.created_at
            await self.upsert_manga(stub)
            added += 1
        return added

    async def get_pending_mangas(self, limit: int) -> list[MangaDocument]:
        pending: list[MangaDocument] = []
        for slug in self._list_manga_slugs():
            manga = await self.get_manga(slug)
            if manga is None:
                continue
            if (
                manga.scrape_status in SYNCABLE_STATUSES
                and manga.attempts < PIPELINE_MAX_RETRIES
            ):
                pending.append(manga)

        pending.sort(key=lambda manga: (
            SYNCABLE_STATUSES.index(manga.scrape_status),
            manga.discovered_at,
        ))
        return pending[:limit]

    async def count_scrape_status(self) -> dict[str, int]:
        counts = {status.value: 0 for status in ScrapeStatus}
        for slug in self._list_manga_slugs():
            manga = await self.get_manga(slug)
            if manga is None:
                continue
            counts[manga.scrape_status.value] += 1
        return counts

    def _load_chapters(self, manga_slug: str) -> dict[str, ChapterDocument]:
        path = self._chapters_path(manga_slug)
        if not path.exists():
            return {}
        raw = json.loads(path.read_text(encoding='utf-8'))
        return {
            chapter_number: ChapterDocument.model_validate(chapter_data)
            for chapter_number, chapter_data in raw.items()
        }

    async def _list_synced_mangas(self) -> list[MangaDocument]:
        synced: list[MangaDocument] = []
        for slug in self._list_manga_slugs():
            manga = await self.get_manga(slug)
            if manga and manga.scrape_status == ScrapeStatus.SYNCED:
                synced.append(manga)
        return synced

    async def get_pending_chapters(self, limit: int) -> list[PendingChapter]:
        synced_mangas = await self._list_synced_mangas()
        chapters_by_manga = {
            manga.slug: self._load_chapters(manga.slug)
            for manga in synced_mangas
        }
        return select_pending_chapters(synced_mangas, chapters_by_manga, limit)

    async def count_pending_chapters(self) -> int:
        return len(await self.get_pending_chapters(limit=10**9))


class FirestoreStore(MangaStore):
    """Firestore-backed store for pipeline discover and sync."""

    def __init__(self) -> None:
        self._db = get_firestore_client()
        self._collection = self._db.collection(MANGAS_COLLECTION)

    def _upsert_manga_sync(self, manga: MangaDocument) -> None:
        manga.updated_at = utcnow()
        payload = manga.model_dump(mode='json')
        self._collection.document(manga.slug).set(payload, merge=True)

    def _upsert_chapter_sync(self, manga_slug: str, chapter: ChapterDocument) -> None:
        payload = chapter.model_dump(mode='json')
        self._collection.document(manga_slug).collection(
            CHAPTERS_SUBCOLLECTION,
        ).document(chapter.chapter_number).set(payload, merge=True)

    def _get_manga_sync(self, slug: str) -> MangaDocument | None:
        snapshot = self._collection.document(slug).get()
        if not snapshot.exists:
            return None
        return MangaDocument.model_validate({**snapshot.to_dict(), 'slug': slug})

    def _enqueue_slugs_sync(self, slugs: list[str]) -> int:
        added = 0
        for slug in slugs:
            doc_ref = self._collection.document(slug)
            snapshot = doc_ref.get()
            if snapshot.exists:
                manga = MangaDocument.model_validate({**snapshot.to_dict(), 'slug': slug})
                if manga.scrape_status != ScrapeStatus.FAILED:
                    continue

            stub = MangaDocument.pending_stub(slug)
            if snapshot.exists:
                existing = MangaDocument.model_validate({**snapshot.to_dict(), 'slug': slug})
                stub.created_at = existing.created_at

            doc_ref.set(stub.model_dump(mode='json'), merge=True)
            added += 1
        return added

    def _get_pending_mangas_sync(self, limit: int) -> list[MangaDocument]:
        pending: list[MangaDocument] = []
        for status in SYNCABLE_STATUSES:
            query = self._collection.where('scrapeStatus', '==', status.value)
            for snapshot in query.stream():
                manga = MangaDocument.model_validate({**snapshot.to_dict(), 'slug': snapshot.id})
                if manga.attempts < PIPELINE_MAX_RETRIES:
                    pending.append(manga)

        pending.sort(key=lambda manga: (
            SYNCABLE_STATUSES.index(manga.scrape_status),
            manga.discovered_at,
        ))
        return pending[:limit]

    def _count_scrape_status_sync(self) -> dict[str, int]:
        counts = {status.value: 0 for status in ScrapeStatus}
        for snapshot in self._collection.stream():
            if not snapshot.exists:
                continue
            data = snapshot.to_dict()
            status = data.get('scrapeStatus', data.get('scrape_status', ScrapeStatus.PENDING.value))
            counts[status] = counts.get(status, 0) + 1
        return counts

    def _load_chapters_sync(self, manga_slug: str) -> dict[str, ChapterDocument]:
        chapters: dict[str, ChapterDocument] = {}
        for snapshot in self._collection.document(manga_slug).collection(
            CHAPTERS_SUBCOLLECTION,
        ).stream():
            if not snapshot.exists:
                continue
            chapters[snapshot.id] = ChapterDocument.model_validate(
                {**snapshot.to_dict(), 'chapter_number': snapshot.id},
            )
        return chapters

    def _list_synced_mangas_sync(self) -> list[MangaDocument]:
        synced: list[MangaDocument] = []
        query = self._collection.where('scrapeStatus', '==', ScrapeStatus.SYNCED.value)
        for snapshot in query.stream():
            synced.append(
                MangaDocument.model_validate({**snapshot.to_dict(), 'slug': snapshot.id}),
            )
        return synced

    def _get_pending_chapters_sync(self, limit: int) -> list[PendingChapter]:
        synced_mangas = self._list_synced_mangas_sync()
        chapters_by_manga = {
            manga.slug: self._load_chapters_sync(manga.slug)
            for manga in synced_mangas
        }
        return select_pending_chapters(synced_mangas, chapters_by_manga, limit)

    async def upsert_manga(self, manga: MangaDocument) -> None:
        await asyncio.to_thread(self._upsert_manga_sync, manga)

    async def upsert_chapter(self, manga_slug: str, chapter: ChapterDocument) -> None:
        await asyncio.to_thread(self._upsert_chapter_sync, manga_slug, chapter)

    async def get_manga(self, slug: str) -> MangaDocument | None:
        return await asyncio.to_thread(self._get_manga_sync, slug)

    async def enqueue_slugs(self, slugs: list[str]) -> int:
        return await asyncio.to_thread(self._enqueue_slugs_sync, slugs)

    async def get_pending_mangas(self, limit: int) -> list[MangaDocument]:
        return await asyncio.to_thread(self._get_pending_mangas_sync, limit)

    async def count_scrape_status(self) -> dict[str, int]:
        return await asyncio.to_thread(self._count_scrape_status_sync)

    async def get_pending_chapters(self, limit: int) -> list[PendingChapter]:
        return await asyncio.to_thread(self._get_pending_chapters_sync, limit)

    async def count_pending_chapters(self) -> int:
        pending = await self.get_pending_chapters(limit=10**9)
        return len(pending)


def get_manga_store() -> MangaStore:
    store_type = os.getenv('PIPELINE_STORE', 'json').lower()
    if store_type == 'firestore':
        return FirestoreStore()
    return JsonFileStore()
