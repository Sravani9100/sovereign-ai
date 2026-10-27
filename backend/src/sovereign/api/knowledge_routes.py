import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from sovereign import audit
from sovereign.api.deps import AdminDep, ApiError, Ctx, CtxDep, Services, not_found
from sovereign.api.schemas import (
    DocumentDetailOut,
    DocumentOut,
    GrantIn,
    GrantOut,
    SpaceIn,
    SpaceOut,
    SpacePatch,
    VersionOut,
)
from sovereign.ingestion import pipeline
from sovereign.ingestion.extract import UnsupportedFile, detect_type
from sovereign.models import (
    Document,
    DocumentVersion,
    KnowledgeSpace,
    Membership,
    PrincipalType,
    SpaceGrant,
    Team,
)
from sovereign.permissions import editable_space_ids, readable_space_ids

router = APIRouter(prefix="/api/v1", tags=["knowledge"])


# Spaces


@router.get("/knowledge/spaces")
def list_spaces(c: CtxDep) -> list[SpaceOut]:
    readable = readable_space_ids(c.session, c.principal)
    editable = editable_space_ids(c.session, c.principal)
    query = select(KnowledgeSpace).where(
        KnowledgeSpace.organization_id == c.principal.organization_id
    )
    if not c.principal.is_admin:  # admins see every space so they can manage access
        query = query.where(KnowledgeSpace.id.in_(readable or [uuid.UUID(int=0)]))
    counts = dict(
        c.session.execute(
            select(Document.space_id, func.count())
            .where(Document.organization_id == c.principal.organization_id)
            .group_by(Document.space_id)
        ).all()
    )
    return [
        SpaceOut(
            id=s.id,
            name=s.name,
            description=s.description,
            classification=s.classification,
            can_read=s.id in readable,
            can_edit=s.id in editable,
            document_count=counts.get(s.id, 0) if s.id in readable else 0,
        )
        for s in c.session.scalars(query.order_by(KnowledgeSpace.name))
    ]


@router.post("/knowledge/spaces", status_code=201)
def create_space(body: SpaceIn, c: AdminDep) -> SpaceOut:
    space = KnowledgeSpace(organization_id=c.principal.organization_id, **body.model_dump())
    c.session.add(space)
    try:
        c.session.flush()
    except IntegrityError:
        raise ApiError(409, "space_exists", "A space with that name already exists") from None
    audit.record(
        c.session,
        "space.created",
        principal=c.principal,
        resource_type="space",
        resource_id=space.id,
        classification=space.classification,
    )
    c.session.commit()
    return SpaceOut(
        id=space.id,
        name=space.name,
        description=space.description,
        classification=space.classification,
        can_read=False,
        can_edit=False,
        document_count=0,
    )


def _space(c: Ctx, space_id: uuid.UUID) -> KnowledgeSpace:
    space = c.session.get(KnowledgeSpace, space_id)
    if space is None or space.organization_id != c.principal.organization_id:
        raise not_found("Space")
    return space


@router.patch("/knowledge/spaces/{space_id}")
def update_space(space_id: uuid.UUID, body: SpacePatch, c: AdminDep) -> SpaceOut:
    space = _space(c, space_id)
    changes = body.model_dump(exclude_none=True)
    for field, value in changes.items():
        setattr(space, field, value)
    # Classification decides which models may see this content: always audit it.
    audit.record(
        c.session,
        "space.updated",
        principal=c.principal,
        resource_type="space",
        resource_id=space.id,
        **changes,
    )
    c.session.commit()
    readable = readable_space_ids(c.session, c.principal)
    editable = editable_space_ids(c.session, c.principal)
    return SpaceOut(
        id=space.id,
        name=space.name,
        description=space.description,
        classification=space.classification,
        can_read=space.id in readable,
        can_edit=space.id in editable,
        document_count=0,
    )


@router.get("/knowledge/spaces/{space_id}/grants")
def list_grants(space_id: uuid.UUID, c: AdminDep) -> list[GrantOut]:
    space = _space(c, space_id)
    grants = c.session.scalars(select(SpaceGrant).where(SpaceGrant.space_id == space.id))
    return [_grant_out(c, g) for g in grants]


def _principal_name(c: Ctx, principal_type: PrincipalType, principal_id: uuid.UUID) -> str | None:
    org = c.principal.organization_id
    match principal_type:
        case PrincipalType.ORGANIZATION:
            return "Everyone" if principal_id == org else None
        case PrincipalType.TEAM:
            team = c.session.get(Team, principal_id)
            return f"Team: {team.name}" if team and team.organization_id == org else None
        case PrincipalType.MEMBER:
            m = c.session.get(Membership, principal_id)
            return m.user.display_name if m and m.organization_id == org else None
    return None


def _grant_out(c: Ctx, grant: SpaceGrant) -> GrantOut:
    return GrantOut(
        id=grant.id,
        principal_type=grant.principal_type,
        principal_id=grant.principal_id,
        principal_name=_principal_name(c, grant.principal_type, grant.principal_id) or "Unknown",
        permission=grant.permission,
    )


@router.post("/knowledge/spaces/{space_id}/grants", status_code=201)
def add_grant(space_id: uuid.UUID, body: GrantIn, c: AdminDep) -> GrantOut:
    space = _space(c, space_id)
    # The principal must belong to this organization: no granting to another tenant's team.
    if _principal_name(c, body.principal_type, body.principal_id) is None:
        raise not_found("Principal")
    grant = c.session.scalar(
        select(SpaceGrant).where(
            SpaceGrant.space_id == space.id,
            SpaceGrant.principal_type == body.principal_type,
            SpaceGrant.principal_id == body.principal_id,
        )
    )
    if grant is None:
        grant = SpaceGrant(organization_id=space.organization_id, space_id=space.id)
        c.session.add(grant)
    grant.principal_type = body.principal_type
    grant.principal_id = body.principal_id
    grant.permission = body.permission
    c.session.flush()
    audit.record(
        c.session,
        "grant.set",
        principal=c.principal,
        resource_type="space",
        resource_id=space.id,
        principal_type=body.principal_type,
        principal_id=body.principal_id,
        permission=body.permission,
        self_grant=body.principal_id == c.principal.membership_id,
    )
    c.session.commit()
    return _grant_out(c, grant)


@router.delete("/knowledge/spaces/{space_id}/grants/{grant_id}", status_code=204)
def remove_grant(space_id: uuid.UUID, grant_id: uuid.UUID, c: AdminDep) -> None:
    space = _space(c, space_id)
    grant = c.session.get(SpaceGrant, grant_id)
    if grant is None or grant.space_id != space.id:
        raise not_found("Grant")
    c.session.delete(grant)
    audit.record(
        c.session,
        "grant.removed",
        principal=c.principal,
        resource_type="space",
        resource_id=space.id,
        principal_type=grant.principal_type,
        principal_id=grant.principal_id,
    )
    c.session.commit()


# Documents


def _latest(document: Document) -> DocumentVersion | None:
    return document.versions[-1] if document.versions else None


def _document_out(document: Document, space_name: str, can_edit: bool) -> DocumentOut:
    latest = _latest(document)
    return DocumentOut(
        id=document.id,
        space_id=document.space_id,
        space_name=space_name,
        title=document.title,
        status=latest.status if latest else "pending",
        current_version_id=document.current_version_id,
        created_at=document.created_at,
        can_edit=can_edit,
    )


@router.get("/documents")
def list_documents(c: CtxDep, space_id: uuid.UUID | None = None) -> list[DocumentOut]:
    readable = readable_space_ids(c.session, c.principal)
    if space_id is not None:
        readable &= {space_id}
    if not readable:
        return []
    editable = editable_space_ids(c.session, c.principal)
    rows = c.session.execute(
        select(Document, KnowledgeSpace.name)
        .join(KnowledgeSpace, KnowledgeSpace.id == Document.space_id)
        .where(
            Document.organization_id == c.principal.organization_id,
            Document.space_id.in_(readable),
        )
        .order_by(Document.title)
    ).all()
    return [_document_out(d, name, d.space_id in editable) for d, name in rows]


def _readable_document(c: Ctx, document_id: uuid.UUID) -> Document:
    document = c.session.get(Document, document_id)
    if (
        document is None
        or document.organization_id != c.principal.organization_id
        or document.space_id not in readable_space_ids(c.session, c.principal)
    ):
        if document is not None:
            audit.record(
                c.session,
                "access.denied",
                principal=c.principal,
                resource_type="document",
                resource_id=document_id,
            )
            c.session.commit()
        raise not_found("Document")
    return document


@router.get("/documents/{document_id}")
def get_document(document_id: uuid.UUID, c: CtxDep) -> DocumentDetailOut:
    document = _readable_document(c, document_id)
    space = c.session.get(KnowledgeSpace, document.space_id)
    can_edit = document.space_id in editable_space_ids(c.session, c.principal)
    base = _document_out(document, space.name, can_edit)
    return DocumentDetailOut(
        **base.model_dump(),
        versions=[VersionOut.model_validate(v) for v in reversed(document.versions)],
    )


async def _read_upload(file: UploadFile, svc: Services) -> tuple[bytes, str]:
    limit = svc.settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise ApiError(413, "too_large", f"Files can be at most {svc.settings.max_upload_mb} MB")
    if not data:
        raise ApiError(422, "empty_file", "The file is empty")
    try:
        return data, detect_type(data, file.filename or "")
    except UnsupportedFile as exc:
        raise ApiError(415, "unsupported_type", str(exc)) from None


def _add_version(c: Ctx, document: Document, data: bytes, mime: str, filename: str):
    key, checksum = c.svc.storage.put(document.organization_id, data)
    version = DocumentVersion(
        organization_id=document.organization_id,
        document_id=document.id,
        version_no=(_latest(document).version_no + 1) if document.versions else 1,
        filename=filename[:300],
        mime_type=mime,
        size_bytes=len(data),
        checksum=checksum,
        storage_key=key,
        uploaded_by=c.principal.membership_id,
    )
    c.session.add(version)
    c.session.flush()
    pipeline.enqueue(c.session, version)
    return version


def _schedule_ingestion(tasks: BackgroundTasks, svc: Services) -> None:
    if svc.settings.inline_ingestion:
        tasks.add_task(pipeline.run_pending, svc.sessions, svc.storage, svc.embedder)


@router.post("/documents", status_code=201)
async def upload_document(
    c: CtxDep,
    tasks: BackgroundTasks,
    space_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form(max_length=300)] = None,
) -> DocumentOut:
    if space_id not in editable_space_ids(c.session, c.principal):
        if space_id in readable_space_ids(c.session, c.principal):
            raise ApiError(403, "forbidden", "You can read this space but not add documents")
        raise not_found("Space")
    data, mime = await _read_upload(file, c.svc)
    filename = file.filename or "upload"
    document = Document(
        organization_id=c.principal.organization_id,
        space_id=space_id,
        title=(title or filename.rsplit(".", 1)[0].replace("_", " ")).strip()[:300],
        created_by=c.principal.membership_id,
    )
    c.session.add(document)
    c.session.flush()
    version = _add_version(c, document, data, mime, filename)
    audit.record(
        c.session,
        "document.uploaded",
        principal=c.principal,
        resource_type="document",
        resource_id=document.id,
        version_id=version.id,
        size_bytes=len(data),
        mime_type=mime,
    )
    c.session.commit()
    c.session.refresh(document)
    _schedule_ingestion(tasks, c.svc)
    space = c.session.get(KnowledgeSpace, space_id)
    return _document_out(document, space.name, True)


@router.post("/documents/{document_id}/versions", status_code=201)
async def upload_version(
    document_id: uuid.UUID,
    c: CtxDep,
    tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
) -> VersionOut:
    document = _readable_document(c, document_id)
    if document.space_id not in editable_space_ids(c.session, c.principal):
        raise ApiError(403, "forbidden", "You can read this document but not change it")
    data, mime = await _read_upload(file, c.svc)
    version = _add_version(c, document, data, mime, file.filename or "upload")
    audit.record(
        c.session,
        "document.version_uploaded",
        principal=c.principal,
        resource_type="document",
        resource_id=document.id,
        version_id=version.id,
    )
    c.session.commit()
    _schedule_ingestion(tasks, c.svc)
    return VersionOut.model_validate(version)


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: uuid.UUID, c: CtxDep) -> None:
    document = _readable_document(c, document_id)
    if document.space_id not in editable_space_ids(c.session, c.principal):
        raise ApiError(403, "forbidden", "You can read this document but not delete it")
    keys = {v.storage_key for v in document.versions}
    c.session.delete(document)  # cascades to versions, chunks, and jobs
    audit.record(
        c.session,
        "document.deleted",
        principal=c.principal,
        resource_type="document",
        resource_id=document.id,
        title=document.title,
    )
    c.session.commit()
    # Files are content-addressed and may be shared with another document.
    for key in keys:
        still_used = c.session.scalar(
            select(func.count())
            .select_from(DocumentVersion)
            .where(DocumentVersion.storage_key == key)
        )
        if not still_used:
            c.svc.storage.delete(key)
