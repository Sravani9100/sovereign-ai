"""Engine, sessions, and tenant context.

Every tenant table has a row-level security policy that only shows rows whose
organization_id matches the `app.org_id` setting of the current transaction. The
application filters by organization explicitly as well; RLS is the second line of
defense, so a forgotten WHERE clause returns nothing instead of another tenant's data.

Every transaction switches to the APP_ROLE database role, which owns nothing and can't
bypass RLS, even when the login role can (managed Postgres admins often have BYPASSRLS).

Sessions come in two kinds:
- tenant sessions (`session.info["org_id"]`): normal request handling
- system sessions (`session.info["system"]`): login, listing a user's organizations, and
  claiming ingestion jobs, which legitimately span tenants
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

APP_ROLE = "sovereign_app"


class Base(DeclarativeBase):
    pass


def normalize_url(url: str) -> str:
    """Accept plain `postgresql://` URLs (as Neon and most hosts print them)."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def make_engine(url: str) -> Engine:
    return create_engine(normalize_url(url), pool_pre_ping=True, pool_recycle=300)


def make_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    factory = sessionmaker(engine, expire_on_commit=False)

    @event.listens_for(factory, "after_begin")
    def _apply_tenant_context(session, _transaction, connection):
        org_id = session.info.get("org_id")
        system = session.info.get("system", False)
        # SET LOCAL and set_config(..., true) are transaction-local, so neither the role nor
        # the tenant can leak to the next user of a pooled connection.
        connection.execute(text(f"SET LOCAL ROLE {APP_ROLE}"))
        connection.execute(
            text(
                "SELECT set_config('app.org_id', :org, true),"
                " set_config('app.bypass_rls', :bypass, true)"
            ),
            {"org": str(org_id) if org_id else "", "bypass": "on" if system else "off"},
        )

    return factory


@contextmanager
def tenant_session(factory: sessionmaker[Session], org_id: uuid.UUID) -> Iterator[Session]:
    with factory() as session:
        session.info["org_id"] = org_id
        yield session


@contextmanager
def system_session(factory: sessionmaker[Session]) -> Iterator[Session]:
    with factory() as session:
        session.info["system"] = True
        yield session
