import json
from abc import ABC, abstractmethod
from pathlib import Path

from app.pipeline.config import PIPELINE_STATE_DIR
from app.pipeline.models import ChapterDocument, MangaDocument, ScrapeStatus, utcnow


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
    """
    Stub for Cloud Functions integration.

    Wire this up with firebase-admin in your Cloud Function:
      - mangas/{slug}
      - mangas/{slug}/chapters/{chapterNumber}
      - mangas/{slug}/chapters/{chapterNumber}/pages/{pageIndex}
    """

    def __init__(self, project_id: str | None = None) -> None:
        self.project_id = project_id

    async def upsert_manga(self, manga: MangaDocument) -> None:
        raise NotImplementedError(
            'Implement with firebase-admin: db.collection("mangas").document(slug).set(...)'
        )

    async def upsert_chapter(self, manga_slug: str, chapter: ChapterDocument) -> None:
        raise NotImplementedError(
            'Implement with firebase-admin: db.collection("mangas").document(slug)'
            '.collection("chapters").document(chapterNumber).set(...)'
        )

    async def get_manga(self, slug: str) -> MangaDocument | None:
        raise NotImplementedError('Implement with firebase-admin get()')
