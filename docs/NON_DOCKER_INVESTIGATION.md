# Non-Docker local development investigation — 13 October 2026

## Native Windows follow-up investigation (before the second implementation)

The user now requires native Windows only. The earlier WSL proposal below is
superseded; retained paragraphs describe the initial investigation, not the current
startup procedure. Current instructions are in NON_DOCKER_LOCAL_DEVELOPMENT.md.

Re-inspection found the same three modified tracked files and two untracked
documentation files from the previous turn, with no frontend changes. They are
preserved and updated in place. No AGENTS.md was found. Existing environment
configuration remains absent: no backend/.env and no configured database, Redis
or GIS process environment keys. Credentials were not printed or guessed.

Native PostgreSQL client is 18.6; postgresql-x64-18 is running and pg_isready
reports accepting connections at 127.0.0.1:5432. No PostGIS control file, GDAL or
GEOS DLL was found in the inspected PostgreSQL 18/OSGeo4W paths; no alternate GIS
installation was found in the top-level installation directories inspected.
No Memurai/Redis service, executable or localhost:6379 listener was found.
Windows Python 3.12.5 and the existing Django 5.2.17/Celery 5.6.3 dependencies
remain installed. No prohibited local runtime was invoked in this follow-up.

Official PostGIS documentation lists PostgreSQL 18 x64 Windows installers
(PostGIS 3.6.x). OSGeo4W supplies native GIS libraries separately for Python.
Memurai's Windows installer supplies a Redis-compatible service; its Developer
edition has license/resource/uptime limits which must be checked against the
chosen release. Hosted Redis is an alternative connection from Windows, but a
fully native local service is the primary documented path. No hosted credentials
or provider endpoint are available for validation.

Celery's FAQ still excludes Windows support. The installed solo pool avoids
prefork/spawn dependencies and runs sequentially, but cannot reproduce production
process isolation, enforced soft/hard time limits or concurrent locking behavior.
Select solo only in native Windows development settings, retain real queued
execution, keep Beat separate, and explicitly document these limitations.
An isolated native worker smoke can test dispatch/retry/Beat using Celery's memory
transport without changing the application's Redis configuration. This cannot
prove actual domain jobs or Redis-backed interprocess operation.

### Native Windows follow-up validation

| Check | Result |
| --- | --- |
| PostgreSQL 18.6 client, native service, pg_isready localhost:5432 | Verified; accepts connections, not authenticated/PostGIS readiness |
| Existing environment dependency consistency (`pip check`) | Passed |
| Python compilation of base/development settings and new smoke script | Passed |
| Explicit GDAL/GEOS paths, DLL-directory deduplication and retained handle (mocked OS loader) | Passed; actual DLL import still blocked |
| Windows development solo/concurrency 1, non-eager execution, PostGIS engine and ten existing Beat entries | Passed as configuration checks |
| Hosted rediss broker/results use CERT_REQUIRED | Passed as configuration check; no hosted endpoint available |
| Production base excludes local GIS/worker-pool overrides | Passed; production deployment files unchanged |
| `backend/scripts/windows_celery_smoke.py` | Passed actual native solo asynchronous dispatch, result retrieval, one retry and Beat Scheduler tick dispatch with private test-only memory transport |
| Django system check | Attempted; exit 1, missing GDAL during startup |
| showmigrations / migrate --plan | Both attempted; exit 1, missing GDAL; no migrations applied |
| makemigrations --check --dry-run | Attempted; exit 1, missing GDAL; no migration files generated |
| Full pytest with config.settings.test_postgresql and unique isolated test name | Attempted; startup exit 1, missing GDAL; no domain tests or test database operations executed |
| Redis PING localhost:6379 databases 0/1/2, retries disabled | Each attempted; TimeoutError; no Redis data modified |
| All 25 guide PowerShell code blocks | Passed PowerShell parser syntax check; installers/startup commands were not executed |
| git diff --check, tracked frontend/production comparisons and untracked inventory | Passed; no frontend/production changes, only the documented new files |

Real PostgreSQL authentication/PostGIS queries, Redis-backed separate worker/Beat,
registered Django tasks, M01–M26 workflows, live email and private media remain
blocked by missing prerequisites. The memory smoke is not a production claim or
application broker replacement. No installer was run, no database or Redis data
was changed and no forbidden local runtime was invoked.

Final file scope: this follow-up updates README, development settings and the two
existing investigation/development documents, and adds the isolated smoke script.
The earlier base settings and .env.example modifications remain preserved.
Frontend paths and production Docker/settings files are unchanged. No staged
changes, commit, push, reset, database deletion or production deployment occurred.

Recorded before implementation. Initial `git status --short` was empty; no uncommitted M23–M26 files were present. No repository AGENTS.md was found. The existing M23–M26 implementation is present in the checkout and must remain intact.

## Authority and architecture

Reviewed SRD v1.3 and Backend Development Guide v1.1 (Word XML text), M23–M26 implementation/validation report and M26 production runbook. PostgreSQL/PostGIS, private S3-compatible files, queued jobs with retries, immutable evidence/audit records, permissions and manual WhatsApp outbox operation remain architectural requirements. Historical test results in the M23–M26 report are not current non-Docker validation.

The active Django project is `backend/manage.py`, `backend/config` and `backend/apps`. Root-level accounts/authorization/audit/config/core are legacy material, not the startup target. Active apps span accounts, roles, localities, identities, properties, listings, media, leads/deals, commissions/payments, verification/site capture, officials/professionals, Free Check, complaints, notifications, administration, marketing and analytics. Tests and migrations live alongside these apps and under `backend/tests`.

## Docker dependency inventory

| Artifact | Purpose | Decision |
| --- | --- | --- |
| `docker-compose.yml` | Optional PostGIS 16/3.5 and Redis 7 services; persistent PostgreSQL volume; host ports | Preserve as an alternative, remove it as required local startup |
| `docker/postgis-init.sql` | Enables PostGIS on first initialization of the Compose database | Preserve; document equivalent administrator action for a native database |
| `backend/Dockerfile`, `.dockerignore`, `requirements-production.txt`, `gunicorn.conf.py` | Linux production runtime with native GIS libraries, pinned dependencies and non-root Gunicorn | Preserve unchanged |
| `docker-compose.production.yml` | Production web, worker, singleton Beat, release checks and static volume, external managed services | Preserve unchanged |
| `docker/backup_database.sh` | PostgreSQL-client backup/archive/checksum utility, usable on a dedicated Linux host | Preserve unchanged |
| README and historic validation reports | README presents Compose first; reports record actual past container tests | Update current instructions; preserve historical evidence |

No active backend code calls Docker or requires its service discovery. `base.py` reads `backend/.env` outside production. `DATABASE_URL` overrides `POSTGRES_*`; Redis cache, broker and results have independent existing URLs (databases 0/1/2). `development.py` inherits installed apps, JWT, middleware, routes and storage. Production ignores the repository `.env` and enforces its existing transport/storage policy.

GeoDjango imports native GDAL/GEOS even before database access. Windows Python 3.12 also requires DLL dependency search directories. Existing settings do not expose environment values for Django's standard GIS library settings. A development-only explicit-path hook is appropriate; no auto-discovery or hardcoded local installation is needed.

`config/celery.py` defaults to development, loads CELERY settings and autodiscovers tasks. Base settings define ten Beat entries: identity expiry, payout due, lost/sold review, aggregates, campaign email, notification email/reminders, verification recalculation/expiry and Full Check deadlines. Keep them, retries and JSON serialization intact. Run workers/Beat in Linux WSL rather than unsupported native Windows. A Linux virtual environment is required because the existing Windows `.venv` cannot run Linux Python.

`pytest.ini` defaults to `config.settings.test_postgresql`; this inherits test-only eager Celery, in-memory cache/email and fast hashing from `test.py` but replaces its Spatialite database with PostGIS. Domain tests therefore do not prove live Redis or asynchronous worker execution. PostgreSQL triggers and locking make SQLite an unsuitable substitute. Tests create/drop a separate test database; never use an existing data database as their target.

Private media supports S3, unconfigured and test-only memory adapters. There is no durable local filesystem adapter to enable. Preserve storage; document S3-compatible service setup as an additional requirement for uploads/reports. Console email is development output, not proof of SMTP delivery.

Frontend inspected read-only: React/TypeScript/Vite, `npm run dev`, strict port 5173, `/api` proxy to `127.0.0.1:8000`, default API base `/api/v1`. No frontend edit is needed.

## Observed local prerequisites

- Existing Windows `.venv`: Python 3.12.5, Django 5.2.17, Celery 5.6.3, psycopg 3.3.6, redis client 6.4.0, pytest 9.1.1.
- Native `postgresql-x64-18` service running; port 5432 listening. This is not proof of database credentials or PostGIS readiness.
- No `backend/.env`; no GIS path environment values. No PostGIS control file or GDAL/GEOS DLLs found in inspected PostgreSQL/OSGeo4W locations.
- No Redis listener at localhost:6379 and no redis CLI on Windows PATH.
- Ubuntu WSL exists; Python present, Redis server/CLI absent.
- No services installed, databases changed, migrations applied, containers/volumes touched or frontend commands run during investigation.

## Implementation boundary

Add explicit GIS library loading to development settings only, document the native PostgreSQL plus WSL Redis/Celery architecture and exact paths, correct current README test/setup statements, and keep the existing environment names and production files. Validation must distinguish syntax/configuration checks from blocked PostgreSQL/Redis/worker workflows. Never claim historical 1,650 passing tests as a result of this change.
