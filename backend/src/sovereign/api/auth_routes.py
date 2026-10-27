from fastapi import APIRouter, BackgroundTasks, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from sovereign import audit, login_codes
from sovereign.api.deps import ApiError, ServicesDep, UserIdDep
from sovereign.api.schemas import (
    CodeRequestIn,
    CodeVerifyIn,
    LoginIn,
    MeOut,
    OrganizationIn,
    OrgMembershipOut,
)
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


def _user_by_email(session, email: str) -> User | None:
    return session.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))


def _start_session(response: Response, user: User, svc) -> None:
    response.set_cookie(
        COOKIE_NAME,
        issue_token(user.id, svc.settings),
        max_age=svc.settings.session_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=svc.settings.cookie_secure,
    )


@router.post("/auth/login")
def login(body: LoginIn, response: Response, svc: ServicesDep) -> MeOut:
    with system_session(svc.sessions) as session:
        user = _user_by_email(session, body.email)
        if not verify_password(body.password, user.password_hash if user else None):
            audit.record(
                session,
                "auth.login_failed",
                actor_user_id=user.id if user else None,
                method="password",
            )
            session.commit()
            raise ApiError(401, "invalid_credentials", "Email or password is incorrect")
        audit.record(session, "auth.login", actor_user_id=user.id, method="password")
        session.commit()
        me = _me(session, user)
    _start_session(response, user, svc)
    return me


@router.post("/auth/code", status_code=202)
def request_code(body: CodeRequestIn, tasks: BackgroundTasks, svc: ServicesDep) -> dict:
    """Email a one-time sign-in code.

    The response is identical whether or not the address has an account, and the email goes
    out after the response, so neither the body nor the timing reveals who is registered.
    """
    email = body.email.strip().lower()
    with system_session(svc.sessions) as session:
        user = _user_by_email(session, email)
        code = login_codes.issue(session, email, svc.settings) if user else None
        if user:
            audit.record(
                session, "auth.code_requested", actor_user_id=user.id, rate_limited=code is None
            )
        session.commit()
    if code:
        minutes = svc.settings.login_code_minutes
        tasks.add_task(
            svc.mailer.send,
            email,
            f"Your SovereignAI sign-in code: {code}",
            f"Your sign-in code is {code}\n\n"
            f"It expires in {minutes} minutes and works once. If you didn't try to sign in, "
            "you can ignore this email.",
        )
    return {"message": "If that address has an account, a sign-in code is on its way."}


@router.post("/auth/code/verify")
def verify_code(body: CodeVerifyIn, response: Response, svc: ServicesDep) -> MeOut:
    email = body.email.strip().lower()
    with system_session(svc.sessions) as session:
        user = _user_by_email(session, email)
        valid = login_codes.verify(session, email, body.code, svc.settings) if user else False
        if not valid:
            audit.record(
                session,
                "auth.login_failed",
                actor_user_id=user.id if user else None,
                method="email_code",
            )
            session.commit()
            raise ApiError(401, "invalid_code", "That code is wrong or has expired")
        audit.record(session, "auth.login", actor_user_id=user.id, method="email_code")
        session.commit()
        me = _me(session, user)
    _start_session(response, user, svc)
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
