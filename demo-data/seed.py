"""Load the demo organizations: python demo-data/seed.py [--reset]

Creates Musterwerk GmbH and RheinTech GmbH with users, teams, knowledge spaces, and
synthetic documents, then indexes everything with the local embedding model.
All demo users share the password printed at the end.
"""

import argparse
import time

from sovereign.ai.embeddings import FastEmbedEmbedder
from sovereign.config import get_settings
from sovereign.db import make_engine, make_sessionmaker
from sovereign.demo import PASSWORD, USERS, reset, seed
from sovereign.storage import LocalStorage


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reset", action="store_true", help="delete all data first")
    args = parser.parse_args()

    settings = get_settings()
    sessions = make_sessionmaker(make_engine(settings.database_url))
    if args.reset:
        reset(sessions)
    started = time.monotonic()
    ids = seed(
        sessions,
        settings,
        LocalStorage(settings.storage_dir),
        FastEmbedEmbedder(settings.embedding_model),
    )
    print(f"Seeded {len(ids.documents)} documents in {time.monotonic() - started:.0f}s.\n")
    print(f"Password for every demo user: {PASSWORD}")
    for email, name in USERS.values():
        print(f"  {name:<14} {email}")


if __name__ == "__main__":
    main()
