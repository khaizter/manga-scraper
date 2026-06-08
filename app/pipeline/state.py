import json
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.pipeline.config import PIPELINE_MAX_RETRIES, PIPELINE_STATE_DIR
from app.pipeline.models import (
    JobStatus,
    JobType,
    PipelineJob,
    QueueItem,
    QueueStatus,
    utcnow,
)


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f'Unsupported type: {type(value)}')


class PipelineState:
    def __init__(self, state_dir: Path | None = None) -> None:
        self.state_dir = state_dir or PIPELINE_STATE_DIR
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.queue_path = self.state_dir / 'queue.json'
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

    def load_queue(self) -> dict[str, QueueItem]:
        raw = self._read_json(self.queue_path, {'items': {}})
        return {
            slug: QueueItem.model_validate(item)
            for slug, item in raw.get('items', {}).items()
        }

    def save_queue(self, queue: dict[str, QueueItem]) -> None:
        self._write_json(
            self.queue_path,
            {'items': {slug: item.model_dump() for slug, item in queue.items()}},
        )

    def enqueue_slugs(self, slugs: list[str]) -> int:
        queue = self.load_queue()
        added = 0
        for slug in slugs:
            if slug in queue and queue[slug].status != QueueStatus.FAILED:
                continue
            queue[slug] = QueueItem(slug=slug)
            added += 1
        self.save_queue(queue)
        return added

    def get_pending_slugs(self, limit: int) -> list[QueueItem]:
        queue = self.load_queue()
        pending = [
            item for item in queue.values()
            if item.status in (QueueStatus.PENDING, QueueStatus.FAILED)
            and item.attempts < PIPELINE_MAX_RETRIES
        ]
        pending.sort(key=lambda item: (item.priority, item.discovered_at))
        return pending[:limit]

    def update_queue_item(self, item: QueueItem) -> None:
        queue = self.load_queue()
        queue[item.slug] = item
        self.save_queue(queue)

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
        jobs['jobs'].insert(0, job.model_dump())
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
                jobs['jobs'][index] = job.model_dump()
                break
        self._write_json(self.jobs_path, jobs)

    def get_status_summary(self) -> dict:
        queue = self.load_queue()
        counts = {status.value: 0 for status in QueueStatus}
        for item in queue.values():
            counts[item.status.value] += 1
        return {
            'queue': counts,
            'dailyProcessed': self.get_daily_processed_count(),
            'queueSize': len(queue),
        }
