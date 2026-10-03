# Oweru Marketplace Backend Foundation

This folder contains the Marketplace M01–M03 backend foundation. The repository has two parts: `backend/` (this Django API) and `frontend/` (the React web app). It is separate from Oweru PA System. Property/listing and transaction workflows are intentionally outside this stage.

## Local setup

Run every command below from the `backend/` folder.

1. Create and activate a Python virtual environment.
2. Install `requirements.txt`.
3. Copy `.env.example` to `.env` and replace `SECRET_KEY` with a private random value.
4. Start PostGIS and Redis with `docker compose up -d db redis` (or configure equivalent services).
5. Apply the initial migrations with `python manage.py migrate`.
6. Start Django with `python manage.py runserver`.

The development database is PostgreSQL with the PostGIS extension enabled; there is no SQLite fallback. The test settings use in-memory SQLite for fast API and model tests. A successful SQLite test run does not establish that a PostGIS server is reachable; `/api/v1/health/ready/` checks both PostGIS and Redis. GeoDjango geometry fields are not used in M01–M03; enabling its backend for later geospatial models also requires native GDAL/GEOS libraries in the runtime image.

## API routes

- `GET /api/v1/`: versioned API root
- `GET /api/v1/health/live/`: process liveness
- `GET /api/v1/health/ready/`: PostGIS and Redis readiness
- `POST /api/v1/auth/register/`: registration (email, phone, full name, password, language; email and phone are both unique)
- `POST /api/v1/auth/login/`: email/password login with lockout (email is case-insensitive)
- `POST /api/v1/auth/token/refresh/`: JWT refresh
- `GET /api/v1/auth/me/`: authenticated account profile
- `POST /api/v1/auth/password/reset/`: request a reset link by email (non-enumerating)
- `POST /api/v1/auth/password/reset/confirm/`: set password with email token
- `/api/schema/` and `/api/docs/`: OpenAPI schema and Swagger UI

The frontend lives in [`../frontend/`](../frontend/README.md).

Roles and permissions extend the existing M03 foundation. Public registration assigns Buyer; public and operational accounts remain separate. JWT-protected Management APIs live under `/api/v1/management/authorization/`. The canonical permission matrix is fixed; only the SRD's optional Verifier/Marketer outbox-send grants can be toggled. Assignment and audit writes are atomic. Admin mutation remains disabled.

See [Backend authorization](doc/BACKEND_AUTHORIZATION.md) for the full catalog/matrix, API contracts, setup command, migration preflight rules, security tests, SRD traceability and deferred object policies. No future Marketplace domain workflows are implemented by these permission codes.

## Tests

Run `pytest`. Django's standard settings check can be run after `.env` is configured with `python manage.py check`. Migrations are kept in each app's `migrations/` directory.

For isolated PostgreSQL integration tests, configure a local test-capable PostgreSQL account and run `pytest --ds=config.settings.test_postgresql`. The default suite remains in-memory SQLite; PostgreSQL-only audit-trigger cases are skipped there.
