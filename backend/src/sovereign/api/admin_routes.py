import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import select, update

from sovereign import audit
from sovereign.api.deps import AdminDep, AdminWriteDep, CtxDep, not_found
from sovereign.api.schemas import AuditEventOut, ModelProfileOut, ModelProfilePatch
from sovereign.models import AuditEvent, ModelProfile, User

router = APIRouter(prefix="/api/v1", tags=["administration"])


def _profile_out(p: ModelProfile) -> ModelProfileOut:
    return ModelProfileOut(
        id=p.id,
        name=p.name,
        provider=p.provider,
        model=p.model,
        max_classification=p.max_classification,
        enabled=p.enabled,
        is_default=p.is_default,
        external=p.external,
    )


@router.get("/model-profiles")
def list_model_profiles(c: CtxDep) -> list[ModelProfileOut]:
    query = select(ModelProfile).where(ModelProfile.organization_id == c.principal.organization_id)
    if not c.principal.is_admin:
        query = query.where(ModelProfile.enabled.is_(True))
    return [_profile_out(p) for p in c.session.scalars(query.order_by(ModelProfile.name))]


@router.patch("/model-profiles/{profile_id}")
def update_model_profile(
    profile_id: uuid.UUID, body: ModelProfilePatch, c: AdminWriteDep
) -> ModelProfileOut:
    profile = c.session.get(ModelProfile, profile_id)
    if profile is None or profile.organization_id != c.principal.organization_id:
        raise not_found("Model profile")
    changes = body.model_dump(exclude_none=True)
    if changes.get("is_default"):
        c.session.execute(
            update(ModelProfile)
            .where(ModelProfile.organization_id == profile.organization_id)
            .values(is_default=False)
        )
    for field, value in changes.items():
        setattr(profile, field, value)
    # Raising an external model's ceiling sends more sensitive data off-premises.
    audit.record(
        c.session,
        "model_profile.updated",
        principal=c.principal,
        resource_type="model_profile",
        resource_id=profile.id,
        external=profile.external,
        **changes,
    )
    c.session.commit()
    return _profile_out(profile)


@router.get("/audit-events")
def list_audit_events(
    c: AdminDep,
    before: datetime | None = None,
    event_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AuditEventOut]:
    query = (
        select(AuditEvent, User.email)
        .outerjoin(User, User.id == AuditEvent.actor_user_id)
        .where(AuditEvent.organization_id == c.principal.organization_id)
    )
    if before:
        query = query.where(AuditEvent.created_at < before)
    if event_type:
        query = query.where(AuditEvent.event_type == event_type)
    rows = c.session.execute(query.order_by(AuditEvent.created_at.desc()).limit(limit))
    return [
        AuditEventOut.model_validate(event).model_copy(update={"actor_email": email})
        for event, email in rows
    ]
