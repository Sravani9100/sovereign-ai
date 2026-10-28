# Security

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub's
[security advisories](https://github.com/Sravani9100/sovereign-ai/security/advisories/new),
not in public issues. Include steps to reproduce. You'll get a reply within a week.

Cross-tenant data access, retrieval of documents a user isn't granted, and confidential
content reaching an external model are the most serious classes of bug in this project.

## Security model

See [Security model](README.md#security-model) in the README. Every claim there is backed by a
test in [`backend/tests/test_security.py`](backend/tests/test_security.py), which runs in CI
against a real Postgres database.

## Not yet implemented

- Malware scanning of uploads (files are type-checked from their bytes, size-limited, and
  parsed with zip-bomb limits, but not virus-scanned).
- OIDC single sign-on. Login is by one-time email code or password (argon2id), behind an
  interface an OIDC provider can replace. Email codes are 6 digits, stored as an HMAC, single
  use, expire after 10 minutes, burn after 5 wrong guesses, and are limited to 3 per address
  per 15 minutes; the request endpoint answers identically for unknown addresses.
- Per-tenant token budgets. (Questions are limited per person per hour and per deployment per
  day; there's no per-IP limit on the sign-in endpoints beyond the per-address code limit.)
- Encryption of provider API keys at rest (keys come from the environment, not the database).
