import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import get_settings
from app.db.models import Job
from app.db.session import session_factory
from app.jobs.pipeline import process_job


def run() -> None:
    settings = get_settings()
    factory = session_factory()
    while True:
        with factory() as db:
            job = db.scalar(
                select(Job)
                .where(Job.status == "queued")
                .order_by(Job.created_at)
                .with_for_update(skip_locked=True)
            )
            if not job:
                time.sleep(settings.poll_seconds)
                continue
            try:
                process_job(db, job, settings)
            except Exception as exc:
                db.rollback()
                failed = db.get(Job, job.id)
                if failed:
                    failed.status = "failed"
                    failed.stage = "failed"
                    failed.error = str(exc)
                    failed.finished_at = datetime.now(timezone.utc)
                    db.commit()


if __name__ == "__main__":
    run()
