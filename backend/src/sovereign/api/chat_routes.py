import json
import time
import uuid
from collections.abc import Iterator
from datetime import timedelta

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sovereign import audit
from sovereign.ai.gateway import ModelError
from sovereign.ai.rag import SYSTEM_PROMPT, build_messages, extract_citations
from sovereign.api.deps import ApiError, Ctx, CtxDep, Services, not_found
from sovereign.api.schemas import (
    CitationOut,
    ConversationDetailOut,
    ConversationIn,
    ConversationOut,
    MessageIn,
    MessageOut,
)
from sovereign.db import system_session, tenant_session
from sovereign.models import (
    Conversation,
    Message,
    MessageCitation,
    MessageRole,
    MessageStatus,
    ModelProfile,
    Organization,
    utcnow,
)
from sovereign.permissions import Principal, readable_space_ids
from sovereign.retrieval import retrieve

router = APIRouter(prefix="/api/v1", tags=["chat"])

DEFAULT_TITLE = "New conversation"


def message_out(message: Message, readable: set[uuid.UUID]) -> MessageOut:
    """Citations to documents the user can no longer read are shown as restricted.

    The answer text itself is kept: it was generated while the user had access. Revocation
    stops new retrievals immediately; it doesn't rewrite history.
    """
    citations = []
    for c in message.citations:
        if c.space_id in readable:
            citations.append(
                CitationOut(
                    marker=c.marker,
                    document_id=c.document_id,
                    document_title=c.document_title,
                    location=c.source_location,
                    quote=c.quote,
                )
            )
        else:
            citations.append(
                CitationOut(
                    marker=c.marker,
                    document_id=None,
                    document_title="Restricted document",
                    location={},
                    quote="",
                    restricted=True,
                )
            )
    return MessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        status=message.status,
        model_profile=message.model_profile,
        model=message.model,
        input_tokens=message.input_tokens,
        output_tokens=message.output_tokens,
        latency_ms=message.latency_ms,
        created_at=message.created_at,
        citations=citations,
    )


def _own_conversation(c: Ctx, conversation_id: uuid.UUID) -> Conversation:
    conversation = c.session.get(Conversation, conversation_id)
    if (
        conversation is None
        or conversation.organization_id != c.principal.organization_id
        or conversation.owner_membership_id != c.principal.membership_id
    ):
        raise not_found("Conversation")
    return conversation


@router.get("/conversations")
def list_conversations(c: CtxDep) -> list[ConversationOut]:
    rows = c.session.scalars(
        select(Conversation)
        .where(
            Conversation.organization_id == c.principal.organization_id,
            Conversation.owner_membership_id == c.principal.membership_id,
        )
        .order_by(Conversation.updated_at.desc())
        .limit(100)
    )
    return [ConversationOut.model_validate(r) for r in rows]


@router.post("/conversations", status_code=201)
def create_conversation(body: ConversationIn, c: CtxDep) -> ConversationOut:
    conversation = Conversation(
        organization_id=c.principal.organization_id,
        owner_membership_id=c.principal.membership_id,
        title=body.title or DEFAULT_TITLE,
    )
    c.session.add(conversation)
    c.session.commit()
    return ConversationOut.model_validate(conversation)


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: uuid.UUID, c: CtxDep) -> ConversationDetailOut:
    conversation = _own_conversation(c, conversation_id)
    readable = readable_space_ids(c.session, c.principal)
    return ConversationDetailOut(
        **ConversationOut.model_validate(conversation).model_dump(),
        messages=[message_out(m, readable) for m in conversation.messages],
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: uuid.UUID, c: CtxDep) -> None:
    c.session.delete(_own_conversation(c, conversation_id))
    c.session.commit()


def _profile(session: Session, org_id: uuid.UUID, name: str | None) -> ModelProfile:
    profiles = session.scalars(
        select(ModelProfile).where(
            ModelProfile.organization_id == org_id, ModelProfile.enabled.is_(True)
        )
    ).all()
    if name is not None:
        for profile in profiles:
            if profile.name == name:
                return profile
        raise ApiError(422, "unknown_model_profile", f"No enabled model profile named '{name}'")
    for profile in sorted(profiles, key=lambda p: not p.is_default):
        return profile
    raise ApiError(409, "no_model", "No model is enabled for this organization")


@router.post("/conversations/{conversation_id}/messages")
def send_message(conversation_id: uuid.UUID, body: MessageIn, c: CtxDep) -> StreamingResponse:
    """Answer a question. Streams server-sent events: status, sources, delta, done, error."""
    conversation = _own_conversation(c, conversation_id)
    profile = _profile(c.session, c.principal.organization_id, body.model_profile)
    _check_limits(c)
    events = _answer(
        c.svc,
        c.principal,
        conversation.id,
        profile.id,
        body.message,
        set(body.knowledge_space_ids) if body.knowledge_space_ids is not None else None,
    )
    return StreamingResponse(
        events,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _check_limits(c: Ctx) -> None:
    """Spending guards, checked before any model call. Each question is one call."""
    settings = c.svc.settings
    now = utcnow()
    asked_last_hour = c.session.scalar(
        select(func.count(Message.id))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.owner_membership_id == c.principal.membership_id,
            Message.role == MessageRole.USER,
            Message.created_at > now - timedelta(hours=1),
        )
    )
    if settings.chat_messages_per_hour and asked_last_hour >= settings.chat_messages_per_hour:
        raise ApiError(
            429,
            "rate_limited",
            f"You've asked {asked_last_hour} questions in the last hour. Please try again later.",
        )
    if settings.daily_message_limit:
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        with system_session(c.svc.sessions) as session:  # counts across all organizations
            asked_today = session.scalar(
                select(func.count(Message.id)).where(
                    Message.role == MessageRole.USER, Message.created_at >= midnight
                )
            )
        if asked_today >= settings.daily_message_limit:
            raise ApiError(
                429,
                "daily_limit",
                "This deployment has reached its daily question limit. Please try again tomorrow.",
            )


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _answer(
    svc: Services,
    principal: Principal,
    conversation_id: uuid.UUID,
    profile_id: uuid.UUID,
    question: str,
    space_ids: set[uuid.UUID] | None,
) -> Iterator[str]:
    started = time.monotonic()
    with tenant_session(svc.sessions, principal.organization_id) as session:
        conversation = session.get(Conversation, conversation_id)
        profile = session.get(ModelProfile, profile_id)
        organization = session.get(Organization, principal.organization_id)
        history = [
            (m.role.value, m.content)
            for m in conversation.messages
            if m.status == MessageStatus.COMPLETE
        ]
        session.add(
            Message(
                organization_id=principal.organization_id,
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=question,
            )
        )
        if conversation.title == DEFAULT_TITLE:
            conversation.title = question[:80]
        conversation.updated_at = utcnow()
        session.commit()

        yield _sse("status", {"stage": "retrieving"})
        sources = retrieve(
            session,
            principal,
            question,
            svc.embedder,
            max_classification=profile.max_classification,
            space_ids=space_ids,
            k=svc.settings.retrieval_k,
            candidates=svc.settings.retrieval_candidates,
            min_similarity=svc.settings.min_similarity,
        )
        yield _sse(
            "sources",
            {"count": len(sources), "profile": profile.name, "external": profile.external},
        )

        parts: list[str] = []
        error: str | None = None
        model_name = profile.model
        usage = None

        def save(status: MessageStatus) -> Message:
            answer, citations = extract_citations("".join(parts), sources)
            message = Message(
                organization_id=principal.organization_id,
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=answer or (error or ""),
                status=status,
                model_profile=profile.name,
                model=model_name,
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
            message.citations = [
                MessageCitation(
                    organization_id=principal.organization_id,
                    marker=cit.marker,
                    chunk_id=cit.chunk.chunk_id,
                    document_id=cit.chunk.document_id,
                    space_id=cit.chunk.space_id,
                    version_id=cit.chunk.version_id,
                    document_title=cit.chunk.document_title,
                    source_location=cit.chunk.location,
                    quote=cit.chunk.content[:1000],
                )
                for cit in citations
            ]
            session.add(message)
            # Metadata only: which documents were used and where the data went, never
            # the question or answer text.
            audit.record(
                session,
                "chat.answered",
                principal=principal,
                resource_type="conversation",
                resource_id=conversation.id,
                model_profile=profile.name,
                provider=profile.provider,
                external=profile.external,
                status=status,
                retrieved_documents=sorted({str(s.document_id) for s in sources}),
                cited_documents=sorted({str(c.chunk.document_id) for c in citations}),
            )
            session.commit()
            return message

        try:
            model = svc.gateway.model_for(profile)
            model_name = model.model
            system = SYSTEM_PROMPT.format(organization=organization.name)
            for text in model.stream(system, build_messages(question, sources, history)):
                parts.append(text)
                yield _sse("delta", {"text": text})
            usage = model.usage
        except ModelError as exc:
            error = str(exc)
        except GeneratorExit:
            # The client went away mid-answer: keep what was generated.
            save(MessageStatus.PARTIAL)
            raise

        if error:
            message = save(MessageStatus.PARTIAL if parts else MessageStatus.ERROR)
            yield _sse("error", {"message": error})
        else:
            message = save(MessageStatus.COMPLETE)
        readable = readable_space_ids(session, principal)
        yield _sse("done", message_out(message, readable).model_dump(mode="json"))
