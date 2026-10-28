import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from sovereign.models import (
    Classification,
    MembershipStatus,
    MessageRole,
    MessageStatus,
    Permission,
    PrincipalType,
    Provider,
    Role,
    VersionStatus,
)


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# Auth & organizations


class LoginIn(BaseModel):
    email: str
    password: str


class CodeRequestIn(BaseModel):
    email: str = Field(max_length=320)


class CodeVerifyIn(BaseModel):
    email: str = Field(max_length=320)
    code: str = Field(pattern=r"^\s*\d{6}\s*$")


class OrgMembershipOut(Out):
    organization_id: uuid.UUID
    name: str
    slug: str
    role: Role


class MeOut(Out):
    id: uuid.UUID
    email: str
    display_name: str
    read_only: bool = False  # a shared demo account while demo mode is on
    organizations: list[OrgMembershipOut]


class OrganizationIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,98}$")


class MemberIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=320)
    display_name: str = Field(min_length=1, max_length=200)
    role: Role = Role.EMPLOYEE
    # Optional: without one, the person signs in with an emailed code.
    password: str | None = Field(default=None, min_length=8)


class MemberPatch(BaseModel):
    role: Role | None = None
    status: MembershipStatus | None = None


class MemberOut(Out):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    display_name: str
    role: Role
    status: MembershipStatus
    team_ids: list[uuid.UUID]


class TeamIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class TeamOut(Out):
    id: uuid.UUID
    name: str
    member_ids: list[uuid.UUID]


# Knowledge


class SpaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    classification: Classification = Classification.INTERNAL


class SpacePatch(BaseModel):
    description: str | None = None
    classification: Classification | None = None


class SpaceOut(Out):
    id: uuid.UUID
    name: str
    description: str
    classification: Classification
    can_read: bool
    can_edit: bool
    document_count: int


class GrantIn(BaseModel):
    principal_type: PrincipalType
    principal_id: uuid.UUID
    permission: Permission = Permission.READ


class GrantOut(Out):
    id: uuid.UUID
    principal_type: PrincipalType
    principal_id: uuid.UUID
    principal_name: str
    permission: Permission


class VersionOut(Out):
    id: uuid.UUID
    version_no: int
    filename: str
    mime_type: str
    size_bytes: int
    status: VersionStatus
    error: str | None
    chunk_count: int
    embedding_model: str | None
    created_at: datetime
    indexed_at: datetime | None


class DocumentOut(Out):
    id: uuid.UUID
    space_id: uuid.UUID
    space_name: str
    title: str
    status: VersionStatus  # of the latest version
    current_version_id: uuid.UUID | None
    created_at: datetime
    can_edit: bool


class DocumentDetailOut(DocumentOut):
    versions: list[VersionOut]


# Chat


class ModelProfileOut(Out):
    id: uuid.UUID
    name: str
    provider: Provider
    model: str
    max_classification: Classification
    enabled: bool
    is_default: bool
    external: bool


class ModelProfilePatch(BaseModel):
    enabled: bool | None = None
    is_default: bool | None = None
    max_classification: Classification | None = None


class ConversationIn(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ConversationOut(Out):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class CitationOut(BaseModel):
    marker: int
    document_id: uuid.UUID | None
    document_title: str
    location: dict
    quote: str
    restricted: bool = False  # the user has since lost access to this document


class MessageOut(BaseModel):
    id: uuid.UUID
    role: MessageRole
    content: str
    status: MessageStatus
    model_profile: str | None
    model: str | None
    input_tokens: int
    output_tokens: int
    latency_ms: int | None
    created_at: datetime
    citations: list[CitationOut]


class ConversationDetailOut(ConversationOut):
    messages: list[MessageOut]


class MessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    model_profile: str | None = None
    # Narrows the search to these spaces. Ids the user can't read are ignored.
    knowledge_space_ids: list[uuid.UUID] | None = None


class AuditEventOut(Out):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    actor_email: str | None = None
    event_type: str
    resource_type: str | None
    resource_id: uuid.UUID | None
    details: dict
    created_at: datetime
