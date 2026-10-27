from alembic import context
from sqlalchemy import create_engine

from sovereign import models  # noqa: F401  (registers tables on Base.metadata)
from sovereign.config import get_settings
from sovereign.db import Base, normalize_url

config = context.config
url = config.attributes.get("database_url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=normalize_url(url), target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(normalize_url(url))
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
