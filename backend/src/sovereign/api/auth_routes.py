from fastapi import APIRouter, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from sovereign import audit
from sovereign.api.deps import ApiError, ServicesDep, UserIdDep
from sovereign.api.schemas import LoginIn, MeOut, OrganizationIn, OrgMembershipOut
from sovereign.auth import COOKIE_NAME, issue_token, verify_password
from sovereign.db import system_session
from sovereign.models import Membership, MembershipStatus, Organization, User
from sovereign.organizations import create_organization

router = APIRouter(prefix="/api/v1", tags=["auth"])


def _me(session, user: User) -> MeOut:
    rows = session.execute(
        select(Membership, Organization)
        .join(Organization, Organization.id == Membership.organization_id)
        .where(Membership.user_id == user.id, Membership.status == MembershipStatus.ACTIVE)
        .order_by(Organization.name)
    ).all()
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        organizations=[
            OrgMembershipOut(organization_id=o.id, name=o.name, slug=o.slug, role=m.role)
            for m, o in rows
        ],
    )


@router.post("/auth/login")
def login(body: LoginIn, response: Response, svc: ServicesDep) -> MeOut:
    with system_session(svc.sessions) as session:
        user = session.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
        if not verify_password(body.password, user.password_hash if user else None):
            audit.record(session, "auth.login_failed", actor_user_id=user.id if user else None)
            session.commit()
            raise ApiError(401, "invalid_credentials", "Email or password is incorrect")
        audit.record(session, "auth.login", actor_user_id=user.id)
        session.commit()
        me = _me(session, user)

    response.set_cookie(
        COOKIE_NAME,
        issue_token(user.id, svc.settings),
        max_age=svc.settings.session_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=svc.settings.cookie_secure,
    )
    return me


@router.post("/auth/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)


@router.get("/auth/me")
def me(user_id: UserIdDep, svc: ServicesDep) -> MeOut:
    with system_session(svc.sessions) as session:
        user = session.get(User, user_id)
        if user is None:
            raise ApiError(401, "unauthenticated", "Sign in to continue")
        return _me(session, user)


@router.post("/organizations", status_code=201)
def create_org(body: OrganizationIn, user_id: UserIdDep, svc: ServicesDep) -> OrgMembershipOut:
    with system_session(svc.sessions) as session:
        user = session.get(User, user_id)
        if user is None:
            raise ApiError(401, "unauthenticated", "Sign in to continue")
        try:
            org, membership = create_organization(
                session, svc.settings, name=body.name, slug=body.slug, owner=user
            )
            audit.record(
                session,
                "organization.created",
                organization_id=org.id,
                actor_user_id=user.id,
                resource_type="organization",
                resource_id=org.id,
            )
            session.commit()
        except IntegrityError:
            raise ApiError(409, "slug_taken", "That organization slug is already taken") from None
        return OrgMembershipOut(
            organization_id=org.id, name=org.name, slug=org.slug, role=membership.role
        )
