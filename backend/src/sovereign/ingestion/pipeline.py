"""The ingestion queue and the work done for each uploaded version.

Jobs live in Postgres and are claimed with FOR UPDATE SKIP LOCKED, so any number of
workers can run without a separate queue service. A job whose worker died is reclaimed
after STALE_AFTER; a failing job is retried up to MAX_ATTEMPTS times.
"""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, text
from sqlalchemy.orm import Session, sessionmaker

from sovereign.ai.embeddings import Embedder
from sovereign.db import system_session, tenant_session
from sovereign.ingestion.chunking import chunk_sections
from sovereign.ingestion.extract import ExtractionError, UnsupportedFile, extract
from sovereign.models import (
    Document,
    DocumentChunk,
    DocumentVersion,
    IngestionJob,
    JobState,
    VersionStatus,
    utcnow,
)
from sovereign.storage import Storage

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
STALE_AFTER = "10 minutes"
EMBED_BATCH = 64


@dataclass(frozen=True)
class ClaimedJob:
    id: uuid.UUID
    organization_id: uuid.UUID
    version_id: uuid.UUID


def enqueue(session: Session, version: DocumentVersion) -> IngestionJob:
    job = IngestionJob(organization_id=version.organization_id, version_id=version.id)
    session.add(job)
    return job


def claim_next(factory: sessionmaker[Session]) -> ClaimedJob | None:
    with system_session(factory) as session:
        row = session.execute(
            text(f"""
                UPDATE ingestion_jobs
                SET state = 'running', attempts = attempts + 1, locked_at = now()
                WHERE id = (
                    SELECT id FROM ingestion_jobs
                    WHERE state = 'queued'
                       OR (state = 'running' AND locked_at < now() - interval '{STALE_AFTER}')
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING id, organization_id, version_id
            """)
        ).one_or_none()
        session.commit()
    return ClaimedJob(*row) if row else None


def process(
    factory: sessionmaker[Session], job: ClaimedJob, storage: Storage, embedder: Embedder
) -> None:
    with tenant_session(factory, job.organization_id) as session:
        version = session.get(DocumentVersion, job.version_id)
        record = session.get(IngestionJob, job.id)
        if version is None or record is None:  # deleted while queued
            return
        version.status = VersionStatus.PROCESSING
        session.commit()

        try:
            count = _index(session, version, storage, embedder)
        except (ExtractionError, UnsupportedFile) as exc:
            # The file itself is the problem; retrying won't help.
            session.rollback()
            _fail(session, version, record, str(exc), retry=False)
            return
        except Exception as exc:
            log.exception("Ingestion failed for version %s", version.id)
            session.rollback()
            _fail(session, version, record, f"{type(exc).__name__}: {exc}", retry=True)
            return

        version.status = VersionStatus.READY
        version.chunk_count = count
        version.embedding_model = embedder.model_name
        version.indexed_at = utcnow()
        version.error = None
        document = session.get(Document, version.document_id)
        current = None
        if document.current_version_id:
            current = session.get(DocumentVersion, document.current_version_id)
        # Only move forward: a slow re-index of v1 must not replace a ready v2.
        if current is None or current.version_no <= version.version_no:
            document.current_version_id = version.id
        record.state = JobState.DONE
        record.error = None
        session.commit()


def _index(session: Session, version: DocumentVersion, storage: Storage, embedder: Embedder) -> int:
    document = session.get(Document, version.document_id)
    sections = extract(storage.get(version.storage_key), version.mime_type)
    chunks = chunk_sections(document.title, sections)

    session.execute(delete(DocumentChunk).where(DocumentChunk.version_id == version.id))
    for start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[start : start + EMBED_BATCH]
        vectors = embedder.embed_documents([c.embedding_text for c in batch])
        session.add_all(
            DocumentChunk(
                organization_id=version.organization_id,
                space_id=document.space_id,
                document_id=document.id,
                version_id=version.id,
                chunk_index=chunk.index,
                context_header=chunk.context_header,
                content=chunk.content,
                source_location=chunk.location,
                embedding=vector,
            )
            for chunk, vector in zip(batch, vectors, strict=True)
        )
    return len(chunks)


def _fail(
    session: Session, version: DocumentVersion, job: IngestionJob, error: str, *, retry: bool
) -> None:
    job.error = error[:2000]
    if retry and job.attempts < MAX_ATTEMPTS:
        job.state = JobState.QUEUED
        version.status = VersionStatus.PENDING
    else:
        job.state = JobState.FAILED
        version.status = VersionStatus.FAILED
        version.error = job.error
    session.commit()


def run_pending(factory: sessionmaker[Session], storage: Storage, embedder: Embedder) -> int:
    """Process queued jobs until none are left. Returns how many were processed."""
    processed = 0
    while job := claim_next(factory):
        process(factory, job, storage, embedder)
        processed += 1
    return processed
