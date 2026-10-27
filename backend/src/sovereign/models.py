import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sovereign.db import Base

EMBEDDING_DIMS = 384  # must match settings.embedding_model; changing it needs a migration


def utcnow() -> datetime:
    return datetime.now(UTC)


def _str_enum(enum: type[StrEnum]) -> Enum:
    return Enum(enum, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e])


JsonB = JSON().with_variant(JSONB(), "postgresql")


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    EMPLOYEE = "employee"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class Classification(StrEnum):
    """How sensitive a knowledge space is. Decides which model providers may see it."""

    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"


class PrincipalType(StrEnum):
    ORGANIZATION = "organization"  # everyone in the organization
    TEAM = "team"
    MEMBER = "member"


class Permission(StrEnum):
    READ = "read"
    EDIT = "edit"  # implies read


class VersionStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Provider(StrEnum):
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    FAKE = "fake"  # tests and offline demos


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"  # client disconnected or generation failed midway
    ERROR = "error"


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, default=uuid.uuid4)


def _org() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = _id()
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = _created()


class User(Base):
    """A global identity. What a user can do is decided per organization by Membership."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _id()
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(String(200))
    external_subject: Mapped[str | None] = mapped_column(String(200), unique=True)  # OIDC sub
    created_at: Mapped[datetime] = _created()


class LoginCode(Base):
    """A one-time sign-in code sent by email. Only an HMAC of the code is stored."""

    __tablename__ = "login_codes"
    __table_args__ = (Index("ix_login_codes_email_created", "email", "created_at"),)

    id: Mapped[uuid.UUID] = _id()
    email: Mapped[str] = mapped_column(String(320))
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = _org()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[Role] = mapped_column(_str_enum(Role))
    status: Mapped[MembershipStatus] = mapped_column(
        _str_enum(MembershipStatus), default=MembershipStatus.ACTIVE
    )
    created_at: Mapped[datetime] = _created()

    user: Mapped[User] = relationship(lazy="joined")


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = _org()
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = _created()


class TeamMember(Base):
    __tablename__ = "team_members"

    organization_id: Mapped[uuid.UUID] = _org()
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memberships.id", ondelete="CASCADE"), primary_key=True
    )


class KnowledgeSpace(Base):
    __tablename__ = "knowledge_spaces"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = _org()
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    classification: Mapped[Classification] = mapped_column(
        _str_enum(Classification), default=Classification.INTERNAL
    )
    created_at: Mapped[datetime] = _created()


class SpaceGrant(Base):
    __tablename__ = "space_grants"
    __table_args__ = (UniqueConstraint("space_id", "principal_type", "principal_id"),)

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = _org()
    space_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_spaces.id", ondelete="CASCADE"), index=True
    )
    principal_type: Mapped[PrincipalType] = mapped_column(_str_enum(PrincipalType))
    # An organization, team, or membership id depending on principal_type.
    principal_id: Mapped[uuid.UUID]
    permission: Mapped[Permission] = mapped_column(_str_enum(Permission))
    created_at: Mapped[datetime] = _created()


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = _org()
    space_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_spaces.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    # The version retrieval uses. Null until the first version is indexed.
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="SET NULL", use_alter=True)
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memberships.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _created()

    versions: Mapped[list["DocumentVersion"]] = relationship(
        foreign_keys="DocumentVersion.document_id",
        order_by="DocumentVersion.version_no",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version_no"),)

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = _org()
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    version_no: Mapped[int]
    filename: Mapped[str] = mapped_column(String(300))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    checksum: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(300))
    status: Mapped[VersionStatus] = mapped_column(
        _str_enum(VersionStatus), default=VersionStatus.PENDING
    )
    error: Mapped[str | None] = mapped_column(Text)
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    chunk_count: Mapped[int] = mapped_column(default=0)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memberships.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _created()
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("version_id", "chunk_index"),
        Index("ix_chunks_org_space", "organization_id", "space_id"),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = _org()
    # Denormalized so retrieval can filter by permitted spaces without joins.
    space_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_spaces.id", ondelete="CASCADE")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int]
    # "Document title > Section heading", prepended for search and shown in citations.
    context_header: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text)
    source_location: Mapped[dict] = mapped_column(JsonB)  # {"page": 3} or {"section": "..."}
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMS))
    tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', context_header || ' ' || content)", persisted=True),
    )


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = _org()
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE")
    )
    state: Mapped[JobState] = mapped_column(_str_enum(JobState), default=JobState.QUEUED)
    attempts: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(Text)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()


class ModelProfile(Base):
    """An approved model an organization's users can pick in chat.

    `max_classification` is the data-egress rule: the most sensitive knowledge space
    whose content may be sent to this model. External APIs are capped at internal by
    default; confidential spaces stay with local models.
    """

    __tablename__ = "model_profiles"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = _org()
    name: Mapped[str] = mapped_column(String(100))
    provider: Mapped[Provider] = mapped_column(_str_enum(Provider))
    model: Mapped[str] = mapped_column(String(100))
    max_classification: Mapped[Classification] = mapped_column(_str_enum(Classification))
    enabled: Mapped[bool] = mapped_column(default=True)
    is_default: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = _created()

    @property
    def external(self) -> bool:
        return self.provider == Provider.ANTHROPIC


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = _org()
    owner_membership_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memberships.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="New conversation")
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _created()

    messages: Mapped[list["Message"]] = relationship(
        order_by="Message.created_at", cascade="all, delete-orphan", passive_deletes=True
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = _org()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MessageRole] = mapped_column(_str_enum(MessageRole))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[MessageStatus] = mapped_column(
        _str_enum(MessageStatus), default=MessageStatus.COMPLETE
    )
    model_profile: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    latency_ms: Mapped[int | None]
    created_at: Mapped[datetime] = _created()

    citations: Mapped[list["MessageCitation"]] = relationship(
        order_by="MessageCitation.marker", cascade="all, delete-orphan", passive_deletes=True
    )


class MessageCitation(Base):
    __tablename__ = "message_citations"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = _org()
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    marker: Mapped[int]  # the [n] in the answer text
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL")
    )
    document_id: Mapped[uuid.UUID]  # no FK: the citation outlives a deleted document
    space_id: Mapped[uuid.UUID]
    version_id: Mapped[uuid.UUID]
    document_title: Mapped[str] = mapped_column(String(300))
    source_location: Mapped[dict] = mapped_column(JsonB)
    quote: Mapped[str] = mapped_column(Text)


class AuditEvent(Base):
    """Append-only: the database has no UPDATE or DELETE policy for this table."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_org_created", "organization_id", "created_at"),)

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(60))
    resource_type: Mapped[str | None] = mapped_column(String(40))
    resource_id: Mapped[uuid.UUID | None]
    details: Mapped[dict] = mapped_column(JsonB, default=dict)
    created_at: Mapped[datetime] = _created()


# Tables protected by row-level security, with the column holding the tenant id.
TENANT_TABLES: dict[str, str] = {
    "organizations": "id",
    "memberships": "organization_id",
    "teams": "organization_id",
    "team_members": "organization_id",
    "knowledge_spaces": "organization_id",
    "space_grants": "organization_id",
    "documents": "organization_id",
    "document_versions": "organization_id",
    "document_chunks": "organization_id",
    "ingestion_jobs": "organization_id",
    "model_profiles": "organization_id",
    "conversations": "organization_id",
    "messages": "organization_id",
    "message_citations": "organization_id",
    "audit_events": "organization_id",
}
