"""Ingestion worker: python -m sovereign.worker

Run any number of these alongside the API (with SOVEREIGN_INLINE_INGESTION=false).
"""

import logging
import time

from sovereign.ai.embeddings import FastEmbedEmbedder
from sovereign.config import get_settings
from sovereign.db import make_engine, make_sessionmaker
from sovereign.ingestion import pipeline
from sovereign.storage import LocalStorage

POLL_SECONDS = 2.0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    sessions = make_sessionmaker(make_engine(settings.database_url))
    storage = LocalStorage(settings.storage_dir)
    embedder = FastEmbedEmbedder(settings.embedding_model)
    log = logging.getLogger("sovereign.worker")
    log.info("Worker started")
    while True:
        if job := pipeline.claim_next(sessions):
            started = time.monotonic()
            pipeline.process(sessions, job, storage, embedder)
            log.info("Processed job %s in %.1fs", job.id, time.monotonic() - started)
        else:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
