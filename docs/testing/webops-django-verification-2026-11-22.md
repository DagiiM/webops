# WebOps Django verification record — 2026-11-22

## Scope

Review branch `fix/webops-django-test-repair-20261122`, based on `feat/runpod-llm-safe-dev`. Verified independently on a private Runpod **CPU-only** development pod using Python 3.11, Django test runner, SQLite test DB, a generated Fernet key, a generated Django secret, and the in-memory background processor. No test was skipped, disabled, converted to expected failure, or removed to obtain a green result.

## Test evidence

1. Original branch/initial environment: 396 discovered tests, 49 failures and 101 errors (partly invalid test environment).
2. After repairs: full source-worktree run **429 tests, zero failures, zero errors, OK**.
3. New **independent clean GitHub checkout** at commit `892e2b8888784cd5abcf68dcf751a46a10e21d89`: full **429 tests in 59.391 seconds, OK**, zero failures/errors/skips.
4. The new checkout successfully applied all migrations on a **new empty SQLite database**, including `databases.0003_database_created_by`.
5. `manage.py check` and `DEBUG=False manage.py check --deploy` both reported **no issues**.
6. Updated previously unimportable database view tests: **19 runnable scenarios**, retaining sixteen legacy scenario names and adding three access-control checks. Tests now exercise current real Django routes instead of importing removed class-based views.
7. MySQL and Mongo optional adapters: declared and installed their actual Python dependencies; the adapter suite passes.
8. Rate limiting, encryption, API authentication, webhook delivery, DB form validation, DB SQL composition, integrations and notifications are covered by active tests.

## Transparent test-fixture corrections

- Fernet generates different ciphertext for the same plaintext: tests verify successful decryption and non-equality rather than deterministic ciphertext.
- Invalid Fernet key test fixtures changed to valid generated Fernet keys; invalid-key paths still retain their negative assertions.
- RGB/HSL tests use actual mathematical values and the full set of ten shade keys (50, 100, ... 900), not contradictory nine-key expectations.
- Mocked account tokens are properly encrypted; tests check soft deletion as inactive/hidden rather than physical removal.
- Database validators are verified against Django's None-on-success and ValidationError-on-failure API.
- Legacy database-view tests were **replaced with functional current-route integration tests**, not deleted or skipped. Authenticated and unauthorized paths are exercised.
- Flaky password-symbol generation was fixed in real production code to securely guarantee each required character class, not by weakening the test.

## Backend fixes

Real PostgreSQL DDL uses `psycopg2.sql.Identifier` for identifiers, parameterized values, autocommit for database CREATE/DROP; development mode no longer pretends writes succeeded. Database view ownership, authenticated credential retrieval, explicit deletion confirmation and proper backend failure propagation were strengthened. Standalone DB ownership gained a `created_by` FK and a migration. Additional fixes cover class-based-view rate-limiter decoration, audit logs, websocket identifiers, trash handling, notifications and server-side token decryption.

## Remaining blockers — not hidden

**Django migration drift remains**: `manage.py makemigrations --check --dry-run --noinput` exits **3** because existing `TwoFactorAuth._secret_encrypted` is a new nonnullable field without a migration/default. This is not part of `manage.py test`, but is a real schema-maintenance issue. Treat it as a release blocker; do not generate a misleading placeholder secret. The existing fresh migrations still ran successfully.

The previous pinned-dependency vulnerability audit found substantial findings. This branch does not resolve those advisories. The suite runs with SQLite and mocked external integrations; it is **not** proof of live PostgreSQL/MySQL/Mongo, production SMTP, public-hosting, or production AI-inference availability. Do not merge or deploy without follow-up migration and dependency security reviews.

## Reproduce

In `control-panel/`, with supported Python environment and dependencies:

```bash
# Generate unique SECRET_KEY and Fernet ENCRYPTION_KEY; never commit them.
export DEBUG=True
export WEBOPS_BG_PROCESSOR=memory
python manage.py check
python manage.py migrate --noinput
python manage.py test --noinput
DEBUG=False python manage.py check --deploy
python manage.py makemigrations --check --dry-run --noinput
```

The final migration command is expected to **fail until the TwoFactorAuth schema drift is repaired**. All 429 test cases succeed.
