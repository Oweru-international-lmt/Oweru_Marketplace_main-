# Oweru Marketplace Backend Foundation

This repository contains the Marketplace M01–M03 backend foundation. It is separate from Oweru PA System. Property/listing and transaction workflows are intentionally outside this stage.

## Local setup

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

The frontend lives in `frontend/` (see its README).

Role and permission assignment is exposed as Python services and managed through the application layer; no public roles or audit mutation API is exposed. Audit model updates and deletes are rejected by model/queryset protections and, in PostgreSQL, a database trigger.

## Tests

Run `pytest`. Django's standard settings check can be run after `.env` is configured with `python manage.py check`. Migrations are kept in each app's `migrations/` directory.
