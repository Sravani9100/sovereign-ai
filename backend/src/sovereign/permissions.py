"""Who can read and edit what.

Access is granted per knowledge space, to the whole organization, a team, or one member.
Admins manage spaces and grants but read documents through grants like everyone else:
an admin who grants themselves access to a confidential space leaves an audit record.

Everything here is resolved from the database on each request, never from the session
token, so removing a grant, a team membership, or a membership takes effect immediately.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from sovereign.models import (
    Classification,
    KnowledgeSpace,
    Membership,
    MembershipStatus,
    Permission,
    PrincipalType,
    Role,
    SpaceGrant,
    TeamMember,
)

_CLASSIFICATION_ORDER = [Classification.INTERNAL, Classification.CONFIDENTIAL]


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    membership_id: uuid.UUID
    organization_id: uuid.UUID
    role: Role
    team_ids: frozenset[uuid.UUID]

    @property
    def is_admin(self) -> bool:
        return self.role in (Role.OWNER, Role.ADMIN)


def load_principal(session: Session, user_id: uuid.UUID, org_id: uuid.UUID) -> Principal | None:
    membership = session.scalar(
        select(Membership).where(
            Membership.organization_id == org_id,
            Membership.user_id == user_id,
            Membership.status == MembershipStatus.ACTIVE,
        )
    )
    if membership is None:
        return None
    team_ids = session.scalars(
        select(TeamMember.team_id).where(
            TeamMember.organization_id == org_id, TeamMember.membership_id == membership.id
        )
    )
    return Principal(
        user_id=user_id,
        membership_id=membership.id,
        organization_id=org_id,
        role=membership.role,
        team_ids=frozenset(team_ids),
    )


def _grant_matches(principal: Principal):
    return or_(
        (SpaceGrant.principal_type == PrincipalType.ORGANIZATION)
        & (SpaceGrant.principal_id == principal.organization_id),
        (SpaceGrant.principal_type == PrincipalType.TEAM)
        & (SpaceGrant.principal_id.in_(principal.team_ids or [uuid.UUID(int=0)])),
        (SpaceGrant.principal_type == PrincipalType.MEMBER)
        & (SpaceGrant.principal_id == principal.membership_id),
    )


def readable_space_ids(
    session: Session,
    principal: Principal,
    max_classification: Classification = Classification.CONFIDENTIAL,
) -> set[uuid.UUID]:
    """Spaces the principal may read, optionally capped by the data-egress classification."""
    allowed = _CLASSIFICATION_ORDER[: _CLASSIFICATION_ORDER.index(max_classification) + 1]
    rows = session.scalars(
        select(SpaceGrant.space_id)
        .join(KnowledgeSpace, KnowledgeSpace.id == SpaceGrant.space_id)
        .where(
            SpaceGrant.organization_id == principal.organization_id,
            KnowledgeSpace.classification.in_(allowed),
            _grant_matches(principal),
        )
    )
    return set(rows)


def editable_space_ids(session: Session, principal: Principal) -> set[uuid.UUID]:
    # Employees only read. Editors and admins edit where they hold an edit grant.
    if principal.role == Role.EMPLOYEE:
        return set()
    rows = session.scalars(
        select(SpaceGrant.space_id).where(
            SpaceGrant.organization_id == principal.organization_id,
            SpaceGrant.permission == Permission.EDIT,
            _grant_matches(principal),
        )
    )
    return set(rows)


def can_read_space(session: Session, principal: Principal, space_id: uuid.UUID) -> bool:
    return space_id in readable_space_ids(session, principal)


def can_edit_space(session: Session, principal: Principal, space_id: uuid.UUID) -> bool:
    return space_id in editable_space_ids(session, principal)
