import threading
import time
import uuid
from decimal import Decimal
from pathlib import Path

from app.config import Settings
from app.jobs.pipeline import (
    DocumentOutcome,
    DocumentTask,
    PendingExtractionRun,
    _run_document_tasks,
)
from app.schemas.domain import DocumentType


def test_document_tasks_run_with_bounded_parallelism(monkeypatch):
    active = 0
    peak = 0
    lock = threading.Lock()

    def fake_process(task: DocumentTask, settings: Settings) -> DocumentOutcome:
        nonlocal active, peak
        del settings
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.08)
        with lock:
            active -= 1
        return DocumentOutcome(
            document_id=task.document_id,
            doc_type=DocumentType.COMMERCIAL_INVOICE,
            classify_confidence=Decimal("1"),
            page_count=1,
            has_text_layer=True,
            ocr_used=False,
            classification=PendingExtractionRun(status="done", parser="classification"),
            extraction=PendingExtractionRun(status="done", parser="test"),
        )

    monkeypatch.setattr("app.jobs.pipeline._process_document", fake_process)
    tasks = [DocumentTask(uuid.uuid4(), Path(f"{index}.pdf")) for index in range(4)]
    settings = Settings(document_concurrency=2, extraction_backend="local")

    started = time.perf_counter()
    outcomes = list(_run_document_tasks(tasks, settings))
    elapsed = time.perf_counter() - started

    assert len(outcomes) == 4
    assert peak == 2
    assert elapsed < 0.28


def test_document_task_failure_does_not_cancel_other_documents(monkeypatch):
    def fake_process(task: DocumentTask, settings: Settings) -> DocumentOutcome:
        del settings
        if task.path.name == "bad.pdf":
            raise RuntimeError("provider unavailable")
        return DocumentOutcome(
            document_id=task.document_id,
            doc_type=DocumentType.PACKING_LIST,
            classify_confidence=Decimal("1"),
            page_count=1,
            has_text_layer=True,
            ocr_used=False,
            classification=PendingExtractionRun(status="done", parser="classification"),
            extraction=PendingExtractionRun(status="done", parser="test"),
        )

    monkeypatch.setattr("app.jobs.pipeline._process_document", fake_process)
    tasks = [
        DocumentTask(uuid.uuid4(), Path("good.pdf")),
        DocumentTask(uuid.uuid4(), Path("bad.pdf")),
    ]

    outcomes = list(
        _run_document_tasks(tasks, Settings(document_concurrency=2, extraction_backend="local"))
    )

    assert len(outcomes) == 2
    failed = next(item for item in outcomes if item.classification.status == "failed")
    assert failed.classification.error == "provider unavailable"
    assert any(item.doc_type == DocumentType.PACKING_LIST for item in outcomes)
