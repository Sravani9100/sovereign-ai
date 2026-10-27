import uuid
from collections import defaultdict

from fastapi import APIRouter
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from sovereign import audit
from sovereign.api.deps import AdminDep, ApiError, CtxDep, not_found
from sovereign.api.schemas import MemberIn, MemberOut, MemberPatch, TeamIn, TeamOut
from sovereign.auth import hash_password
from sovereign.models import Membership, MembershipStatus, Role, Team, TeamMember, User

router = APIRouter(prefix="/api/v1", tags=["organization"])


def _team_ids_by_member(session, org_id) -> dict[uuid.UUID, list[uuid.UUID]]:
    result: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for team_id, membership_id in session.execute(
        select(TeamMember.team_id, TeamMember.membership_id).where(
            TeamMember.organization_id == org_id
        )
    ):
        result[membership_id].append(team_id)
    return result


def _member_out(m: Membership, team_ids: list[uuid.UUID]) -> MemberOut:
    return MemberOut(
        id=m.id,
        user_id=m.user_id,
        email=m.user.email,
        display_name=m.user.display_name,
        role=m.role,
        status=m.status,
        team_ids=team_ids,
    )


@router.get("/members")
def list_members(c: AdminDep) -> list[MemberOut]:
    org = c.principal.organization_id
    teams = _team_ids_by_member(c.session, org)
    members = c.session.scalars(
        select(Membership).join(User).where(Membership.organization_id == org).order_by(User.email)
    )
    return [_member_out(m, teams.get(m.id, [])) for m in members]


@router.post("/members", status_code=201)
def add_member(body: MemberIn, c: AdminDep) -> MemberOut:
    if body.role == Role.OWNER and c.principal.role != Role.OWNER:
        raise ApiError(403, "forbidden", "Only owners can add owners")
    session = c.session
    user = session.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    if user is None:
        if not body.password:
            raise ApiError(422, "password_required", "New users need an initial password")
        user = User(
            email=body.email.lower(),
            display_name=body.display_name,
            password_hash=hash_password(body.password),
        )
        session.add(user)
        session.flush()
    membership = Membership(
        organization_id=c.principal.organization_id, user_id=user.id, role=body.role
    )
    session.add(membership)
    try:
        session.flush()
    except IntegrityError:
        raise ApiError(409, "already_member", "That user is already a member") from None
    audit.record(
        session,
        "member.added",
        principal=c.principal,
        resource_type="membership",
        resource_id=membership.id,
        role=body.role,
    )
    session.commit()
    session.refresh(membership)
    return _member_out(membership, [])


@router.patch("/members/{membership_id}")
def update_member(membership_id: uuid.UUID, body: MemberPatch, c: AdminDep) -> MemberOut:
    session = c.session
    membership = session.get(Membership, membership_id)
    if membership is None or membership.organization_id != c.principal.organization_id:
        raise not_found("Member")
    if membership.id == c.principal.membership_id:
        raise ApiError(400, "cannot_change_self", "You can't change your own role or access")
    protected = (Role.OWNER, Role.ADMIN)
    if c.principal.role != Role.OWNER and (membership.role in protected or body.role in protected):
        raise ApiError(403, "forbidden", "Only owners can change admins and owners")

    changes = body.model_dump(exclude_none=True)
    for field, value in changes.items():
        setattr(membership, field, value)
    event = "member.revoked" if body.status == MembershipStatus.REVOKED else "member.updated"
    audit.record(
        session,
        event,
        principal=c.principal,
        resource_type="membership",
        resource_id=membership.id,
        **changes,
    )
    session.commit()
    teams = _team_ids_by_member(session, c.principal.organization_id)
    return _member_out(membership, teams.get(membership.id, []))


@router.get("/teams")
def list_teams(c: CtxDep) -> list[TeamOut]:
    org = c.principal.organization_id
    members: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for team_id, membership_id in c.session.execute(
        select(TeamMember.team_id, TeamMember.membership_id).where(
            TeamMember.organization_id == org
        )
    ):
        members[team_id].append(membership_id)
    teams = c.session.scalars(select(Team).where(Team.organization_id == org).order_by(Team.name))
    # Employees see team names, not who is in which team.
    show = c.principal.is_admin
    return [TeamOut(id=t.id, name=t.name, member_ids=members[t.id] if show else []) for t in teams]


@router.post("/teams", status_code=201)
def create_team(body: TeamIn, c: AdminDep) -> TeamOut:
    team = Team(organization_id=c.principal.organization_id, name=body.name)
    c.session.add(team)
    try:
        c.session.flush()
    except IntegrityError:
        raise ApiError(409, "team_exists", "A team with that name already exists") from None
    audit.record(
        c.session,
        "team.created",
        principal=c.principal,
        resource_type="team",
        resource_id=team.id,
        name=body.name,
    )
    c.session.commit()
    return TeamOut(id=team.id, name=team.name, member_ids=[])


def _team_and_member(c, team_id, membership_id) -> tuple[Team, Membership]:
    org = c.principal.organization_id
    team = c.session.get(Team, team_id)
    membership = c.session.get(Membership, membership_id)
    if team is None or team.organization_id != org:
        raise not_found("Team")
    if membership is None or membership.organization_id != org:
        raise not_found("Member")
    return team, membership


@router.put("/teams/{team_id}/members/{membership_id}", status_code=204)
def add_team_member(team_id: uuid.UUID, membership_id: uuid.UUID, c: AdminDep) -> None:
    team, membership = _team_and_member(c, team_id, membership_id)
    if c.session.get(TeamMember, (team.id, membership.id)) is None:
        c.session.add(
            TeamMember(
                organization_id=team.organization_id, team_id=team.id, membership_id=membership.id
            )
        )
        audit.record(
            c.session,
            "team.member_added",
            principal=c.principal,
            resource_type="team",
            resource_id=team.id,
            membership_id=membership.id,
        )
        c.session.commit()


@router.delete("/teams/{team_id}/members/{membership_id}", status_code=204)
def remove_team_member(team_id: uuid.UUID, membership_id: uuid.UUID, c: AdminDep) -> None:
    team, membership = _team_and_member(c, team_id, membership_id)
    c.session.execute(
        delete(TeamMember).where(
            TeamMember.team_id == team.id, TeamMember.membership_id == membership.id
        )
    )
    audit.record(
        c.session,
        "team.member_removed",
        principal=c.principal,
        resource_type="team",
        resource_id=team.id,
        membership_id=membership.id,
    )
    c.session.commit()
