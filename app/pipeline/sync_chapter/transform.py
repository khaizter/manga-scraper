from app.pipeline.config import PIPELINE_STORE
from app.pipeline.models import ChapterDocument, ScrapeStatus, chapter_page_storage_path, utcnow
from app.pipeline.sync_chapter.types import ChapterExtractResult, PageUpload, SyncChapterLoadItem
from app.services.storage import MIME_EXTENSIONS, parse_data_uri


def transform_chapter(extract: ChapterExtractResult) -> SyncChapterLoadItem:
    """Shape scraped pages into upload payloads and a chapter document."""
    if not extract.page_data_uris or not any(extract.page_data_uris):
        raise ValueError('No chapter pages found')

    if PIPELINE_STORE != 'firestore':
        raise ValueError('Chapter page upload requires PIPELINE_STORE=firestore')

    pages: list[PageUpload] = []
    storage_paths: list[str] = []

    for page_index, data_uri in enumerate(extract.page_data_uris):
        if not data_uri:
            storage_paths.append('')
            continue

        mime, data = parse_data_uri(data_uri)
        extension = MIME_EXTENSIONS.get(mime, 'jpg')
        storage_path = chapter_page_storage_path(
            extract.manga_slug,
            extract.chapter.chapter_number,
            page_index,
            extension,
        )
        pages.append(PageUpload(storage_path=storage_path, data=data, content_type=mime))
        storage_paths.append(storage_path)

    chapter = ChapterDocument(
        chapter_number=extract.chapter.chapter_number,
        chapter_slug=extract.chapter.chapter_slug,
        storage_paths=storage_paths,
        scrape_status=ScrapeStatus.SYNCED,
        last_synced_at=utcnow(),
    )

    return SyncChapterLoadItem(
        manga_slug=extract.manga_slug,
        chapter=chapter,
        pages=pages,
    )
