"""Report internal model usage without exposing it in the end-user interface."""

from __future__ import annotations

import argparse

from sqlalchemy import func, select

from app.db.models import Dispatch, Document, Job
from app.db.session import session_factory


def main() -> None:
    parser = argparse.ArgumentParser(description="Uso interno de modelos por ejecución")
    parser.add_argument("--limit", type=int, default=10, help="Cantidad de ejecuciones recientes")
    args = parser.parse_args()
    limit = max(1, min(args.limit, 100))

    with session_factory()() as db:
        document_count = (
            select(func.count(Document.id))
            .where(Document.dispatch_id == Job.dispatch_id)
            .correlate(Job)
            .scalar_subquery()
        )
        rows = db.execute(
            select(Job, Dispatch, document_count.label("document_count"))
            .join(Dispatch, Dispatch.id == Job.dispatch_id)
            .order_by(Job.created_at.desc())
            .limit(limit)
        ).all()

    headers = (
        "job_id",
        "despacho",
        "estado",
        "pdfs",
        "segundos",
        "pdfs_minuto",
        "tokens_entrada",
        "tokens_salida",
        "tokens_total",
        "costo_usd",
    )
    print("\t".join(headers))
    for job, dispatch, document_count in rows:
        elapsed = ""
        documents_per_minute = ""
        if job.started_at and job.finished_at:
            elapsed_seconds = (job.finished_at - job.started_at).total_seconds()
            elapsed = f"{elapsed_seconds:.1f}"
            if elapsed_seconds > 0:
                documents_per_minute = f"{document_count * 60 / elapsed_seconds:.1f}"
        print(
            "\t".join(
                (
                    str(job.id),
                    dispatch.despacho_no or "",
                    job.status,
                    str(document_count),
                    elapsed,
                    documents_per_minute,
                    str(job.tokens_in),
                    str(job.tokens_out),
                    str(job.tokens_in + job.tokens_out),
                    str(job.cost_usd),
                )
            )
        )


if __name__ == "__main__":
    main()
