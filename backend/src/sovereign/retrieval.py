"""Permission-aware hybrid retrieval.

Authorization happens first: the permitted space ids are resolved for the principal and
the model profile's data-egress ceiling, and both searches only ever see chunks in those
spaces. Nothing is retrieved globally and filtered afterwards, so content the user may not
read never reaches ranking, the prompt, or the model.

Ranking fuses a vector search (meaning) with a full-text search (exact terms such as error
codes and section numbers) using reciprocal rank fusion.
"""

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sovereign.ai.embeddings import Embedder
from sovereign.models import Classification, Document, DocumentChunk
from sovereign.permissions import Principal, readable_space_ids

RRF_K = 60


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    version_id: uuid.UUID
    space_id: uuid.UUID
    document_title: str
    context_header: str
    content: str
    location: dict
    score: float


def retrieve(
    session: Session,
    principal: Principal,
    query: str,
    embedder: Embedder,
    *,
    max_classification: Classification,
    space_ids: set[uuid.UUID] | None = None,
    k: int = 8,
    candidates: int = 30,
    min_similarity: float = 0.55,
) -> list[RetrievedChunk]:
    allowed = readable_space_ids(session, principal, max_classification)
    if space_ids is not None:
        allowed &= space_ids  # a client can narrow its search, never widen it
    if not allowed or not query.strip():
        return []

    scope = (
        select(DocumentChunk.id)
        .join(Document, Document.current_version_id == DocumentChunk.version_id)
        .where(
            DocumentChunk.organization_id == principal.organization_id,
            DocumentChunk.space_id.in_(allowed),
        )
    )

    distance = DocumentChunk.embedding.cosine_distance(embedder.embed_query(query))
    vector_hits = [
        chunk_id
        for chunk_id, dist in session.execute(
            scope.add_columns(distance).order_by(distance).limit(candidates)
        )
        if 1 - dist >= min_similarity
    ]

    keyword_hits: list[uuid.UUID] = []
    if terms := _or_query(query):
        tsquery = func.to_tsquery("english", terms)
        keyword_hits = list(
            session.scalars(
                scope.where(DocumentChunk.tsv.op("@@")(tsquery))
                .order_by(func.ts_rank_cd(DocumentChunk.tsv, tsquery).desc())
                .limit(candidates)
            )
        )

    scores: dict[uuid.UUID, float] = {}
    for hits in (vector_hits, keyword_hits):
        for rank, chunk_id in enumerate(hits):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (RRF_K + rank + 1)
    top = sorted(scores, key=scores.__getitem__, reverse=True)[:k]
    if not top:
        return []

    rows = session.execute(
        select(DocumentChunk, Document.title)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.id.in_(top))
    ).all()
    by_id = {chunk.id: (chunk, title) for chunk, title in rows}
    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            version_id=chunk.version_id,
            space_id=chunk.space_id,
            document_title=title,
            context_header=chunk.context_header,
            content=chunk.content,
            location=chunk.source_location,
            score=round(scores[chunk.id], 5),
        )
        for chunk, title in (by_id[i] for i in top if i in by_id)
    ]


def _or_query(query: str) -> str:
    """Any-term tsquery. websearch_to_tsquery requires every word, which almost never
    matches a natural-language question."""
    words = dict.fromkeys(w.lower() for w in re.findall(r"[A-Za-z0-9]+", query) if len(w) > 1)
    return " | ".join(words)
