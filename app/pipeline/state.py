import json
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

from app.pipeline.config import PIPELINE_STATE_DIR
from app.pipeline.models import JobStatus, JobType, PipelineJob, utcnow
from app.pipeline.store import MangaStore, get_manga_store


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f'Unsupported type: {type(value)}')


class PipelineState:
    def __init__(
        self,
        state_dir: Path | None = None,
        manga_store: MangaStore | None = None,
    ) -> None:
        self.state_dir = state_dir or PIPELINE_STATE_DIR
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.manga_store = manga_store or get_manga_store()
        self.jobs_path = self.state_dir / 'jobs.json'
        self.daily_path = self.state_dir / 'daily.json'

    def _read_json(self, path: Path, default: dict) -> dict:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding='utf-8'))

    def _write_json(self, path: Path, data: dict) -> None:
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=_json_default),
            encoding='utf-8',
        )

    def get_daily_processed_count(self) -> int:
        today = date.today().isoformat()
        raw = self._read_json(self.daily_path, {'days': {}})
        return int(raw.get('days', {}).get(today, 0))

    def increment_daily_processed(self, count: int = 1) -> int:
        today = date.today().isoformat()
        raw = self._read_json(self.daily_path, {'days': {}})
        days = raw.setdefault('days', {})
        days[today] = int(days.get(today, 0)) + count
        self._write_json(self.daily_path, raw)
        return days[today]

    def start_job(self, job_type: JobType, config: dict) -> PipelineJob:
        jobs = self._read_json(self.jobs_path, {'jobs': []})
        job = PipelineJob(id=str(uuid4()), type=job_type, config=config)
        jobs['jobs'].insert(0, job.model_dump(mode='json'))
        jobs['jobs'] = jobs['jobs'][:50]
        self._write_json(self.jobs_path, jobs)
        return job

    def update_job(self, job: PipelineJob, status: JobStatus, stats: dict) -> None:
        job.status = status
        job.completed_at = utcnow()
        job.stats = stats
        jobs = self._read_json(self.jobs_path, {'jobs': []})
        for index, stored in enumerate(jobs.get('jobs', [])):
            if stored.get('id') == job.id:
                jobs['jobs'][index] = job.model_dump(mode='json')
                break
        self._write_json(self.jobs_path, jobs)

    async def get_status_summary(self) -> dict:
        counts = await self.manga_store.count_scrape_status()
        pending_chapters = await self.manga_store.count_pending_chapters()
        return {
            'scrapeStatus': counts,
            'pendingChapters': pending_chapters,
            'dailyProcessed': self.get_daily_processed_count(),
            'mangaCount': sum(counts.values()),
        }
