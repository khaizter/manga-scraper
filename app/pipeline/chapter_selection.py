from app.pipeline.models import ChapterDocument, MangaDocument, PendingChapter, ScrapeStatus, chapter_needs_sync
from app.services.chapters_api import CHAPTER_SLUG_PREFIX


def pending_chapters_for_manga(
    manga: MangaDocument,
    existing_chapters: dict[str, ChapterDocument],
) -> list[PendingChapter]:
    """Return unsynced chapters for one manga, in manga.chapters order."""
    # chapter_order maps chapter numbers to their index in manga.chapters, e.g.:
    # {"336-2": 0, "336-1": 1, "1": 2}
    chapter_order: dict[str, int] = {}
    for index, number in enumerate(manga.chapters):
        chapter_order[number] = index

    pending: list[PendingChapter] = []
    for chapter_number in manga.chapters:
        # Check if chapter document exists for this chapter number.
        chapter = existing_chapters.get(chapter_number)
        if chapter is None:
            # If not, create a new chapter document.
            chapter = ChapterDocument(
                chapter_number=chapter_number,
                chapter_slug=f'{CHAPTER_SLUG_PREFIX}{chapter_number}',
            )

        # If the chapter needs to be synced, add it to the pending list.
        if chapter_needs_sync(chapter):
            pending.append(PendingChapter(manga_slug=manga.slug, chapter=chapter))

    # Sort pending chapters by their order in the manga.chapters list.
    pending.sort(key=lambda item: chapter_order.get(item.chapter.chapter_number, 0))
    return pending


def select_pending_chapters(
    synced_mangas: list[MangaDocument],
    chapters_by_manga: dict[str, dict[str, ChapterDocument]],
    limit: int,
) -> list[PendingChapter]:
    """
    Select chapters that still need page uploads.

    Rules:
      - Parent manga scrapeStatus must be synced (metadata + chapter list done).
      - Chapter scrapeStatus is not synced, or chapter subdoc is missing.
      - Walk manga.chapters in list order; oldest discovered manga first.
    """
    synced_mangas.sort(key=lambda manga: manga.discovered_at)
    pending: list[PendingChapter] = []

    for manga in synced_mangas:
        if manga.scrape_status != ScrapeStatus.SYNCED:
            continue

        for item in pending_chapters_for_manga(
            manga,
            chapters_by_manga.get(manga.slug, {}),
        ):
            pending.append(item)
            if len(pending) >= limit:
                return pending

    return pending
