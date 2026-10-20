# Oweru Marketplace Backend Foundation

## Documentation

Start here:

- [AGENTS.md](AGENTS.md): rules, commands and conventions for everyone changing this repository
- [docs/srd.md](docs/srd.md): the build specification (SRD v1.3)
- [docs/prd.md](docs/prd.md): the product requirements (PRD v1.8)
- [docs/architecture-essentials.md](docs/architecture-essentials.md) and [docs/architecture.md](docs/architecture.md): how the system is built and what is done
- [docs/design.md](docs/design.md): the visual system and screen patterns

M10–M13 backend workflows and operational contracts are documented in
[Leads, Deals, Commission, Payments and Payouts](docs/M10_M13_BACKEND.md).
The current default test configuration is PostgreSQL/PostGIS; run it in a
GIS-capable environment. Earlier foundation-only descriptions below are historical.

This repository contains the Marketplace M01–M26 backend implementation. It is
separate from Oweru PA System. See the
[M23–M26 implementation report](docs/M23_M26_IMPLEMENTATION_AND_VALIDATION.md)
for the current scope and validation boundaries.

## Local setup

Follow [Non-Docker local development on Windows](docs/NON_DOCKER_LOCAL_DEVELOPMENT.md)
for the existing virtual environment, native PostgreSQL/PostGIS, Windows GIS
libraries, native Windows Memurai (Redis-compatible) or hosted Redis, a development
Celery solo worker, migration review, Django and npm commands. Local development
uses native Windows only. Existing production deployment files are preserved.

Development and the default test suite use PostgreSQL/PostGIS. GeoDjango requires
native GDAL/GEOS libraries. `/api/v1/health/ready/` checks PostGIS and the Redis
cache; separate checks are required for asynchronous Celery execution and storage.

## API routes

- `GET /api/v1/`: versioned API root
- `GET /api/v1/health/`: lightweight application availability
- `GET /api/v1/health/live/`: process liveness
- `GET /api/v1/health/ready/`: PostGIS and Redis readiness
- `POST /api/v1/auth/register/`: registration (email, phone, full name, password, language; email and phone are both unique)
- `POST /api/v1/auth/login/`: email/password login with lockout (email is case-insensitive)
- `POST /api/v1/auth/token/refresh/`: JWT refresh
- `GET /api/v1/auth/me/`: authenticated account profile
- `POST /api/v1/auth/password/reset/`: request a reset link by email (non-enumerating)
- `POST /api/v1/auth/password/reset/confirm/`: set password with email token
- `/api/v1/schema/`, `/api/v1/docs/`, and `/api/v1/redoc/`: OpenAPI schema, Swagger UI, and ReDoc

The frontend lives in `frontend/` (see its README).

Roles and permissions extend the existing M03 foundation. Public registration assigns Buyer; public and operational accounts remain separate. JWT-protected Management APIs live under `/api/v1/management/authorization/`. The canonical permission matrix is fixed; only the SRD's optional Verifier/Marketer outbox-send grants can be toggled. Assignment and audit writes are atomic. Admin mutation remains disabled.

See [Backend authorization](docs/backend_authorization/BACKEND_AUTHORIZATION.md) for the catalog/matrix, API contracts, setup command, migration preflight rules, security tests and SRD traceability. Domain workflows extend this foundation through the existing backend apps.

## Tests

From `backend/`, run `pytest`. Django's standard settings check can be run after `backend/.env` is configured with `python manage.py check`. Migrations are kept in each app's `migrations/` directory.

For isolated PostgreSQL integration tests, configure a test-capable PostgreSQL
account and run `pytest --ds=config.settings.test_postgresql` from `backend/`.
This is also the default test settings module. Tests use a separate disposable
database, an in-memory cache and eager Celery; they do not establish live worker
or Redis readiness. Follow the guide's isolation checks before running them.
