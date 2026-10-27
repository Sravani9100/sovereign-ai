"""Audit records: who did what, never the content of documents or questions."""

import uuid

from sqlalchemy.orm import Session

from sovereign.models import AuditEvent
from sovereign.permissions import Principal


def record(
    session: Session,
    event_type: str,
    *,
    principal: Principal | None = None,
    organization_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    **details,
) -> None:
    session.add(
        AuditEvent(
            organization_id=principal.organization_id if principal else organization_id,
            actor_user_id=principal.user_id if principal else actor_user_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details={k: _jsonable(v) for k, v in details.items()},
        )
    )


def _jsonable(value):
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, list | tuple | set | frozenset):
        return [_jsonable(v) for v in value]
    return value
