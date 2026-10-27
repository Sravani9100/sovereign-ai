import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from sovereign.ai.embeddings import Embedder
from sovereign.ai.gateway import Gateway
from sovereign.auth import COOKIE_NAME, read_token
from sovereign.config import Settings
from sovereign.db import tenant_session
from sovereign.permissions import Principal, load_principal
from sovereign.storage import Storage


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status, self.code, self.message = status, code, message


def not_found(what: str = "Resource") -> ApiError:
    # Used for "exists but you may not see it" too, so ids can't be probed.
    return ApiError(404, "not_found", f"{what} not found")


@dataclass
class Services:
    settings: Settings
    sessions: object  # sessionmaker
    storage: Storage
    embedder: Embedder
    gateway: Gateway


def services(request: Request) -> Services:
    return request.app.state.services


def current_user_id(request: Request, svc: Annotated[Services, Depends(services)]) -> uuid.UUID:
    token = request.cookies.get(COOKIE_NAME)
    auth = request.headers.get("authorization", "")
    if not token and auth.lower().startswith("bearer "):
        token = auth[7:]
    user_id = read_token(token, svc.settings) if token else None
    if user_id is None:
        raise ApiError(401, "unauthenticated", "Sign in to continue")
    return user_id


@dataclass
class Ctx:
    session: Session
    principal: Principal
    svc: Services


def ctx(
    user_id: Annotated[uuid.UUID, Depends(current_user_id)],
    svc: Annotated[Services, Depends(services)],
    organization_id: Annotated[uuid.UUID, Header(alias="X-Organization-Id")],
) -> Iterator[Ctx]:
    with tenant_session(svc.sessions, organization_id) as session:
        principal = load_principal(session, user_id, organization_id)
        if principal is None:
            raise ApiError(403, "not_a_member", "You are not an active member of this organization")
        yield Ctx(session, principal, svc)


def admin_ctx(c: Annotated[Ctx, Depends(ctx)]) -> Ctx:
    if not c.principal.is_admin:
        raise ApiError(403, "forbidden", "Only organization admins can do this")
    return c


CtxDep = Annotated[Ctx, Depends(ctx)]
AdminDep = Annotated[Ctx, Depends(admin_ctx)]
ServicesDep = Annotated[Services, Depends(services)]
UserIdDep = Annotated[uuid.UUID, Depends(current_user_id)]
