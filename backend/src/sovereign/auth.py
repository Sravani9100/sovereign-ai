"""Password login and session tokens.

The token only says who the user is. Which organization they act in comes from a header
and is checked against an active membership on every request, so a revoked member is
locked out on their next request even with an unexpired token.

An OIDC provider (Keycloak, Entra ID) can replace password login by mapping its subject to
User.external_subject; nothing downstream of `current_user_id` changes.
"""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from sovereign.config import Settings

COOKIE_NAME = "sovereign_session"
_hasher = PasswordHasher()
# Verifying against a dummy hash for unknown emails keeps login timing uniform.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and bool(password_hash)
    except (VerifyMismatchError, InvalidHashError):
        return False


def issue_token(user_id: uuid.UUID, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(hours=settings.session_hours),
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm="HS256")


def read_token(token: str, settings: Settings) -> uuid.UUID | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["sub", "exp"]},
        )
        return uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None
