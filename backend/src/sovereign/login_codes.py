"""One-time sign-in codes sent by email.

- 6 digits, valid for `login_code_minutes`, single use.
- Stored as an HMAC keyed with the server secret, so a database leak doesn't reveal live codes.
- 5 wrong guesses burn the code; requesting a new code cancels the previous one.
- At most 3 codes per address per 15 minutes, so the endpoint can't be used to flood an inbox.
"""

import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from sovereign.config import Settings
from sovereign.models import LoginCode, utcnow

MAX_ATTEMPTS = 5
MAX_CODES_PER_WINDOW = 3
WINDOW = timedelta(minutes=15)


def _digest(email: str, code: str, settings: Settings) -> str:
    key = settings.jwt_secret.get_secret_value().encode()
    return hmac.new(key, f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def issue(session: Session, email: str, settings: Settings) -> str | None:
    """Create a code for `email`, or return None when the address is rate limited."""
    now = utcnow()
    recent = session.scalar(
        select(func.count())
        .select_from(LoginCode)
        .where(LoginCode.email == email, LoginCode.created_at > now - WINDOW)
    )
    if recent >= MAX_CODES_PER_WINDOW:
        return None
    session.execute(
        update(LoginCode)
        .where(LoginCode.email == email, LoginCode.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    code = f"{secrets.randbelow(1_000_000):06d}"
    session.add(
        LoginCode(
            email=email,
            code_hash=_digest(email, code, settings),
            expires_at=now + timedelta(minutes=settings.login_code_minutes),
        )
    )
    return code


def verify(session: Session, email: str, code: str, settings: Settings) -> bool:
    now = utcnow()
    latest = session.scalar(
        select(LoginCode)
        .where(LoginCode.email == email, LoginCode.consumed_at.is_(None))
        .order_by(LoginCode.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if latest is None or latest.expires_at <= now:
        return False
    latest.attempts += 1
    if hmac.compare_digest(latest.code_hash, _digest(email, code.strip(), settings)):
        latest.consumed_at = now
        return True
    if latest.attempts >= MAX_ATTEMPTS:
        latest.consumed_at = now  # burned: request a new one
    return False
