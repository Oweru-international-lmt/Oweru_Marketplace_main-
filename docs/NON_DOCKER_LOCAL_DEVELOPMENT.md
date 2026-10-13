# Oweru Marketplace: native Windows local development

## Status and architecture

All local processes run natively on Windows. Django uses the existing Windows
`.venv`, PostgreSQL 18/PostGIS runs as a Windows service, Memurai supplies the
Redis protocol, Celery uses a development-only solo worker plus separate Beat,
and the unchanged frontend runs through npm. No WSL, Ubuntu, local Linux runtime,
Docker Desktop or Compose is part of local development. A hosted Redis connection
from native Windows is an optional external service; native Memurai is primary.
Private files still require the existing private S3-compatible storage adapter.
No database fallback, synchronous Celery substitution or frontend change is made.

See [the pre-change investigation](NON_DOCKER_INVESTIGATION.md) for the Docker
inventory, authority review, native Windows follow-up and settings analysis.
Local Compose files are retained for history, not offered as a local alternative.
Production Dockerfile,
Compose, pinned requirements, Gunicorn and backup files are retained unchanged.
Historical container test results remain historical evidence.

Observed on 13 October 2026: native PostgreSQL 18.6 client/service and port 5432 are up;
database authentication/PostGIS are unverified. Windows Python dependencies are
present. GDAL/GEOS, PostGIS, a configured `backend/.env` and a Redis-compatible service
still require setup. Django check and PostgreSQL pytest were attempted and both
stopped at missing GDAL before any application test executed. No migrations,
database resets, Docker operations, frontend installation or deployment occurred.

## Required software

| Component | Baseline |
| --- | --- |
| Windows Python | Existing 64-bit Python 3.12 `.venv` (observed 3.12.5) |
| Django/DRF | Existing requirements: Django 5.2.x, DRF >=3.16,<4 |
| Database | Native PostgreSQL 18.6 installed; matching pg18 x64 PostGIS 3.6.x Windows bundle required; its full suite is not validated |
| Windows GIS | Compatible 64-bit GDAL, GEOS and PROJ from OSGeo4W, plus their data files; select a version supported by Django 5.2 |
| Redis | Native Memurai for Redis Windows x64 Developer edition or a compatible dedicated hosted endpoint |
| Workers | Existing Windows Python 3.12 venv, Celery 5.6.3 solo/concurrency 1; officially unsupported Windows runtime, development only |
| Frontend | Existing package-lock and package.json; Node version satisfying installed Vite's engines (inspect below) |
| Files/email | Private S3-compatible storage for durable uploads/PDFs; console email for development or configured SMTP for actual delivery |

Official prerequisites: [GeoDjango installation](https://docs.djangoproject.com/en/5.2/ref/contrib/gis/install/),
[PostGIS setup](https://postgis.net/documentation/getting_started/),
[Memurai Windows installation](https://docs.memurai.com/en/installation).
[Celery does not support native Windows](https://docs.celeryq.dev/en/stable/faq.html#windows).
Use the tested isolated native `--pool=solo` development workaround below.
It does not reproduce production process isolation, time limits or concurrency.

## Windows Python and environment

Run these PowerShell commands in each backend terminal:

```powershell
Set-Location 'D:\my codes\Oweru_Marketplace-main'
. .\.venv\Scripts\Activate.ps1
python -m pip install -r .\backend\requirements.txt
python -m pip check
if (-not (Test-Path -LiteralPath .\backend\.env)) {
    Copy-Item -LiteralPath .\backend\.env.example -Destination .\backend\.env
}
notepad .\backend\.env
$env:DJANGO_SETTINGS_MODULE = 'config.settings.development'
Set-Location .\backend
```

If activation is blocked by local policy, use `..\.venv\Scripts\python.exe`
from `backend/` in place of `python`; do not change machine execution policy.
Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`
and paste it into the ignored `backend/.env`. Do not share the output.

Keep `.env` private; `git check-ignore backend/.env` from the repository root
must confirm it is ignored. Do not overwrite an existing file or copy production
credentials. Existing process environment values take precedence over dotenv.
Explicitly select development in each terminal; `manage.py` and Celery also
default to development. Production does not load this file.

Use the existing keys, replacing placeholders with actual local values:

```powershell
# Enter these values in ignored backend/.env using the editor; do not execute them.
# DJANGO_SETTINGS_MODULE=config.settings.development
# SECRET_KEY=REPLACE_WITH_PRIVATE_RANDOM_VALUE
# DEBUG=true
# ALLOWED_HOSTS=localhost,127.0.0.1,testserver
# POSTGRES_DB=oweru_marketplace
# POSTGRES_USER=oweru
# POSTGRES_PASSWORD=REPLACE_WITH_EXISTING_LOCAL_PASSWORD
# POSTGRES_HOST=127.0.0.1
# POSTGRES_PORT=5432
# REDIS_URL=redis://localhost:6379/0
# CELERY_BROKER_URL=redis://localhost:6379/1
# CELERY_RESULT_BACKEND=redis://localhost:6379/2
# CORS_ALLOWED_ORIGINS=http://localhost:5173
# CSRF_TRUSTED_ORIGINS=http://localhost:5173
# EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
# DEFAULT_FROM_EMAIL=no-reply@oweru.local
# MARKETPLACE_PUBLIC_URL=http://localhost:5173
# PASSWORD_RESET_URL=http://localhost:5173/reset-password
# EMAIL_VERIFICATION_URL=http://localhost:5173/verify-email
```

Use the actual existing database/user if different. Leave `POSTGRES_ENGINE`
unset to retain PostGIS. Either use the discrete POSTGRES keys or `DATABASE_URL`;
an existing `DATABASE_URL` overrides all connection fields. URL credentials must
be percent encoded. `REDIS_PORT` in Compose is not a Django setting: change the
port inside each Redis URL instead. Hosted Redis must support the selected logical
databases; use service-approved authenticated/TLS URLs and certificate verification.

## PostgreSQL/PostGIS without database reset

Keep the existing PostgreSQL 18 installation and databases. The
[official Windows releases](https://postgis.net/documentation/getting_started/install_windows/released_versions/)
provide PostgreSQL 18 x64 PostGIS 3.6.x bundles. Launch Stack Builder, select the
existing PostgreSQL 18 x64/5432 instance, choose Spatial Extensions and its PostGIS
bundle, and install into `C:\Program Files\PostgreSQL\18`. Deselect optional sample
database creation. Do not initialize a data directory or choose a different server
major version. If Stack Builder is absent, use the matching pg18 x64 installer from
the official release page with the same choices. Setup needs administrator access.
No installer is run automatically by this change.

```powershell
$stackBuilder = 'C:\Program Files\PostgreSQL\18\bin\stackbuilder.exe'
Test-Path -LiteralPath $stackBuilder
# Launch interactively when present:
& $stackBuilder
```

PowerShell (actual installed 18 client path on this machine):

```powershell
Get-Service -Name 'postgresql-x64-18'
# Only if this intended local service is stopped; an elevated shell may be required:
Start-Service -Name 'postgresql-x64-18'
$psql = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
& $psql -h 127.0.0.1 -p 5432 -U oweru -d oweru_marketplace -W -c 'SELECT current_database(), current_user, version();'
& $psql -h 127.0.0.1 -p 5432 -U oweru -d oweru_marketplace -W -c "SELECT name, default_version, installed_version FROM pg_available_extensions WHERE name = 'postgis';"
& $psql -h 127.0.0.1 -p 5432 -U oweru -d oweru_marketplace -W -c 'SELECT PostGIS_Full_Version();'
```

Passwords are prompted, not supplied on the command line. If the database/role
does not exist, have the local administrator provision a new empty database and
role with a private password; do not recreate any existing database. In the
confirmed intended development database, an administrator can enable the installed
extension once, without deleting data:

```powershell
& $psql -h 127.0.0.1 -p 5432 -U postgres -d oweru_marketplace -W -c 'CREATE EXTENSION IF NOT EXISTS postgis;'
```

The application role needs access to its database/schema and ownership/DDL
privileges for its migrations. Use a dedicated local test role with CREATEDB
and a DBA-provisioned PostGIS test template if it cannot create the extension.
`POSTGRES_TEST_TEMPLATE` is optional; it must name a real template containing
PostGIS. The previous example's template name was not proof it existed.
Do not run tests as a production superuser.

## Windows GIS configuration

Install OSGeo4W's coherent 64-bit GDAL/GEOS/PROJ packages and data dependencies,
separately from the PostGIS server extension. Download the
[official installer](https://trac.osgeo.org/osgeo4w/) from PowerShell:

```powershell
$gisSetup = Join-Path $env:TEMP 'osgeo4w-setup.exe'
Invoke-WebRequest 'https://download.osgeo.org/osgeo4w/v2/osgeo4w-setup.exe' -OutFile $gisSetup
& $gisSetup --help
& $gisSetup --advanced --root 'C:\OSGeo4W' --site 'https://download.osgeo.org/osgeo4w/v2/' --packages 'gdal,geos,proj'
```

Choose Advanced Install, Install from Internet, x64, root `C:\OSGeo4W`, official
download site and gdal/geos/proj with their required dependencies. Administrator
access may be needed. Do not choose package removal or mix DLLs from unrelated GIS
distributions. [Installer switches](https://trac.osgeo.org/osgeo4w/wiki/CommandLine)
and [Django GIS versions](https://docs.djangoproject.com/en/5.2/ref/contrib/gis/install/)
are authoritative; actual imports must still be validated. No GIS pip binding or
replacement Python interpreter is required by GeoDjango. Discover actual files:

```powershell
Get-ChildItem 'C:\OSGeo4W\bin\gdal*.dll','C:\OSGeo4W\bin\geos_c.dll'
```

Add actual paths to `backend/.env` (the DLL filename below is a placeholder):

```powershell
# Enter these values in ignored backend/.env using the editor; do not execute them.
# GDAL_LIBRARY_PATH=C:/OSGeo4W/bin/ACTUAL_GDAL_DLL.dll
# GEOS_LIBRARY_PATH=C:/OSGeo4W/bin/geos_c.dll
# GDAL_DATA=C:/OSGeo4W/share/gdal
# PROJ_LIB=C:/OSGeo4W/share/proj
```

These are standard Django GIS settings/library environment names, not new
application service names. Non-production base settings now read the two library
paths and retain Python DLL-directory handles on Windows. GDAL_DATA/PROJ_LIB
are consumed by native libraries after dotenv loading. Paths must point to real
matching 64-bit libraries with their dependencies. Production behavior is unchanged.

From `backend/` with the existing venv active:

```powershell
python -c "import django; django.setup(); from django.contrib.gis.geos import Point; from django.contrib.gis.gdal import GDAL_VERSION; print(GDAL_VERSION, Point(39, -6, srid=4326))"
python manage.py check --settings=config.settings.development
python manage.py showmigrations --settings=config.settings.development
python manage.py migrate --plan --settings=config.settings.development
python manage.py makemigrations --check --dry-run --settings=config.settings.development
```

Review the target and migration plan, and back up any valued data before applying
forward migrations. Apply only after that review:

```powershell
python manage.py migrate --settings=config.settings.development
```

No `flush`, reverse migrations, `--fake`, drop/recreate or automatic migration is
part of startup. Existing financial/audit/evidence triggers must remain intact.

## Native Redis-compatible service: Memurai

Install **Memurai for Redis, Windows x64 Developer edition** from the
[vendor download page](https://www.memurai.com/get-memurai). Choose the Windows
Redis-compatible MSI, not a different product/platform package. Record the actual
downloaded filename and inspect its signature:

```powershell
$memuraiMsi = Read-Host 'Full path to the downloaded Memurai Windows MSI'
Get-AuthenticodeSignature -LiteralPath $memuraiMsi | Format-List Status,SignerCertificate
# Elevated PowerShell, after reviewing the downloaded installer:
& msiexec.exe /i $memuraiMsi INSTALL_SERVICE=1 PORT=6379 ADD_FIREWALL_RULE=0
```

Follow its dialogs, select C:\Program Files\Memurai, service installation, port
6379 and no firewall exception. Retain loopback binding/protected mode. Do not
overwrite an existing service's configuration or persistence. Wait for setup to
finish. [Installer options](https://docs.memurai.com/en/installation) document
these properties. No installer was run in this change; no new Python dependency
is needed.

Developer edition is licensed for development/testing, not production, and stops
after ten days. The current download page also lists host-count/memory limits;
check the chosen release/license. Version claims differ between the vendor FAQ
and download page: record actual INFO server output rather than assuming a
specific Redis version. A restart interruption can affect queued jobs.

```powershell
Get-Service -Name '*Memurai*'
# Use the actual service name shown; normally Memurai:
Start-Service -Name 'Memurai'
& 'C:\Program Files\Memurai\memurai-cli.exe' -h 127.0.0.1 -p 6379 ping
& 'C:\Program Files\Memurai\memurai-cli.exe' -h 127.0.0.1 -p 6379 INFO server
```

Retain the existing three URLs on localhost:6379 databases 0/1/2. If the port or
authentication differs, edit each URL in ignored backend/.env. Do not use FLUSHDB,
FLUSHALL, queue purge or remove persistence files.

## Optional hosted Redis from native Windows

Use a dedicated development endpoint compatible with Django and Celery commands,
including blocking lists, transactions, expiration and Pub/Sub. REST-only services
are insufficient. Prefer a non-cluster Redis service with logical databases 0/1/2.
If only database 0 is supported, use three isolated development endpoints instead
of sharing production namespaces or assuming Redis Cluster compatibility.

Put provider URLs into the existing REDIS_URL, CELERY_BROKER_URL and
CELERY_RESULT_BACKEND keys, with rediss://, encoded credentials and the provider's
port. Development settings verify Celery broker/result certificates for rediss;
Django's Redis client verifies TLS by default. Private CAs need reviewed trust
configuration. Do not use ssl_cert_reqs=none. No hosted endpoint/credentials were
available for validation.

From the native Windows backend terminal, check all three connections without
printing passwords or changing Redis data:

```powershell
@'
import os
from dotenv import load_dotenv
from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry
load_dotenv('.env')
pairs = [('REDIS_URL','redis://localhost:6379/0'), ('CELERY_BROKER_URL','redis://localhost:6379/1'), ('CELERY_RESULT_BACKEND','redis://localhost:6379/2')]
for key, default in pairs:
    try:
        client = Redis.from_url(os.getenv(key, default), socket_connect_timeout=3, socket_timeout=3, retry=Retry(NoBackoff(), 0))
        print(key, 'PASS' if client.ping() else 'FAIL')
        client.close()
    except Exception as exc:
        print(key, 'FAIL', type(exc).__name__)
'@ | python -B -
```

## Native Celery worker and Beat: development only

Celery officially does not support Windows. The solo pool is a limited native
development workaround, not a supported or production-ready worker runtime.
Windows development settings select solo/concurrency=1; explicit CLI flags below
make that choice visible. Real Redis-backed execution stays asynchronous and
existing retry/task/Beat logic remains intact. No eager override is introduced.

Solo executes one task at a time. It lacks prefork process isolation, enforced
soft/hard time limits and child recycling. The existing 270/300-second limits
remain configured but cannot be enforced by solo. A blocked task blocks its
worker/control replies. Use bounded I/O timeouts and small synthetic development
workloads. A result.get timeout limits the caller's wait, not the task's runtime.
Native solo does not validate concurrency/row-locking, production recovery or
worker timeout behavior. See [Celery pool features](https://docs.celeryq.dev/en/stable/userguide/concurrency/).
No eventlet/gevent or unnecessary dependency is added.

Use the same existing Windows .venv and backend/.env in every terminal. In a
configured backend PowerShell terminal:

```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.settings.development'
python -m celery -A config worker --pool=solo --concurrency=1 --loglevel=INFO
```

In a second configured backend terminal, start exactly one Beat:

```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.settings.development'
$beatState = Join-Path $env:LOCALAPPDATA 'OweruMarketplace\celery'
New-Item -ItemType Directory -Path $beatState -Force | Out-Null
python -m celery -A config beat --loglevel=INFO --schedule (Join-Path $beatState 'celerybeat-schedule')
```

All ten existing schedules remain: identity expiry, payout due, lost/sold review,
market aggregates, campaign email, notification delivery/reminders, verification
recalculation/expiry and Full Check deadlines. Start Beat only against the intended
local database with safe email/storage settings: jobs may change records or send
email. Do not run duplicate Beat instances or connect local workers to production
data/queues. Production settings and deployment files are unchanged.

## Django and unchanged frontend

From the configured Windows backend terminal:

```powershell
python manage.py runserver 127.0.0.1:8000 --settings=config.settings.development
```

In another PowerShell terminal:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/health/live/'
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/health/ready/'
```

Readiness verifies PostGIS and cache Redis, not migrations, SMTP, media or workers.
JWT, middleware, permissions, API routes and all apps remain in the existing settings.

Frontend commands for the developer (not executed in this change):

```powershell
Set-Location 'D:\my codes\Oweru_Marketplace-main\frontend'
node --version
node -p "require('./package-lock.json').packages['node_modules/vite'].engines"
npm.cmd ci
npm.cmd run dev
```

Use Node satisfying the displayed lockfile engines. `npm ci` installs the existing
lockfile dependencies. Visit `http://localhost:5173`; Vite proxies `/api` to
`http://127.0.0.1:8000`. Existing VITE_API_BASE_URL defaults to `/api/v1`.
No frontend environment/configuration edits are required. Do not run formatters,
dependency upgrades or asset generation as part of this backend change.

## Private files and email

Keep existing S3-compatible storage: set `MEDIA_STORAGE_BACKEND=s3`, the existing
`MEDIA_STORAGE_BUCKET`, and `MEDIA_STORAGE_ENDPOINT` when applicable. Supply
credentials through the existing boto3 provider chain; grant only access to a
dedicated private development bucket. The worker must receive the same storage
configuration and credentials. Preserve signed URLs and access controls.
The default `unconfigured` adapter deliberately rejects object operations; `memory`
is test-only and loses data across processes. Neither is a complete local media
service. Durable uploads, verification evidence and PDF workflows require the
configured object service and remain unverified here.

Console email prints locally; it does not prove receipt. To test real delivery,
configure existing EMAIL_HOST/PORT/USER/PASSWORD/USE_TLS/USE_SSL and
DEFAULT_FROM_EMAIL for a development SMTP service and consenting test recipients.
Never send an actual campaign as a smoke test. WhatsApp remains manual via the
existing outbox. No SMS or automatic WhatsApp service is introduced.

## PostgreSQL domain tests and separate asynchronous smoke

Run only after GIS and independently available PostGIS are confirmed. Use a
dedicated local test role, with a provisioned PostGIS template if required.
The default PostgreSQL test settings inherit an in-memory cache/email and eager
Celery; this isolates tests and is not the development execution mode.

To avoid collisions with any existing test database, select a new unique test
base name in a disposable terminal. `DATABASE_URL` must be cleared so it cannot
override this name. The generated base database need not contain application data;
Django creates `test_<name>` via the PostgreSQL maintenance connection. The test
role must connect to the `postgres` maintenance database and create a database.

```powershell
Set-Location 'D:\my codes\Oweru_Marketplace-main'
. .\.venv\Scripts\Activate.ps1
Set-Location .\backend
$env:DJANGO_SETTINGS_MODULE = 'config.settings.test_postgresql'
$env:DATABASE_URL = ''
$env:POSTGRES_DB = 'oweru_validation_' + [guid]::NewGuid().ToString('N')
# Set POSTGRES_USER/PASSWORD to the dedicated local test account in this terminal
# or an ignored environment file; do not put credentials in shell history.
python -m pytest --ds=config.settings.test_postgresql
```

Do not use `--reuse-db`, `--create-db`, `--keepdb` or run concurrent suites against
the same name. If asked to delete an existing test database, stop and investigate.
Django normally removes only its newly created disposable test database at the end;
no pre-existing database deletion is authorized. Close this terminal afterward so
test configuration cannot leak into normal startup.

The full suite covers authentication/permissions, properties/listings/public search,
leads/deals, commissions/payments, verification, Free/Full Check, complaints,
notifications, marketing, analytics, management/settings, migrations/triggers and
concurrency. Missing services or GIS block the suite; do not substitute SQLite.

### Isolated native Windows smoke (no external services)

The added smoke script starts a real native solo worker, queues JSON work, verifies
execution in a different thread from the producer, retries once and verifies a
Beat Scheduler tick dispatching another task. It never imports Django, accesses
domain records or sends email. Its private memory transport/result backend exists
only inside the smoke script; application settings still use Redis.

```powershell
Set-Location 'D:\my codes\Oweru_Marketplace-main'
. .\.venv\Scripts\Activate.ps1
python -B .\backend\scripts\windows_celery_smoke.py
```

Passed on native Windows/Python 3.12.5/Celery 5.6.3: asynchronous dispatch,
result retrieval, one retry and Beat tick dispatch with eager=False. This does not
validate Redis-backed interprocess operation, persistent Beat or Django domain jobs.

### Real Redis/Django integration (after prerequisites)

From a development backend terminal, verify existing scheduled task registration:

```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.settings.development'
python -c "import django; django.setup(); from config.celery import app; app.loader.import_default_modules(); assert not app.conf.task_always_eager; tasks=[x['task'] for x in app.conf.beat_schedule.values()]; assert len(tasks)==10 and all(t in app.tasks for t in tasks); print('All scheduled tasks registered')"
```

For an asynchronous smoke without invoking a domain task or sending email, start
a separate native worker consuming only a smoke queue; do not start Beat for this
smoke and ensure no other producer uses this queue:

```powershell
python -m celery -A config worker --pool=solo --concurrency=1 --loglevel=INFO --queues=oweru_local_smoke --hostname=oweru-smoke@%h
```

From a normal **development** Windows backend terminal, use Celery's built-in
accumulator task to prove publish, native worker execution and result retrieval:

```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.settings.development'
python -c "import django; django.setup(); from config.celery import app; assert not app.conf.task_always_eager; result=app.send_task('celery.accumulate', args=['oweru-local-smoke'], kwargs={'index': 0}, queue='oweru_local_smoke'); print(result.id, result.get(timeout=30)); assert result.state == 'SUCCESS'"
```

The built-in accumulator should return `oweru-local-smoke`. Confirm SUCCESS and the matching
task ID in the smoke worker log. This tests transport/execution without accessing
domain records; it does not establish real domain job outcomes or email delivery.
If the installed Celery does not register that built-in task, do not enqueue
production tasks as a substitute; inspect registration first. Use the normal
worker on a synthetic development database and consenting test recipients for
end-to-end notification retry/periodic job acceptance.

## Safe stopping

Stop Beat first with Ctrl+C in its terminal, then workers with one Ctrl+C and
wait for warm shutdown/task completion. Stop Django and Vite with Ctrl+C. Avoid
force-killing a worker while it is delivering email. Once users/workers have stopped,
stop only the dedicated Memurai service started for this development session,
in an elevated PowerShell terminal:

```powershell
Stop-Service -Name 'Memurai'
```

Memurai's service stop uses its configured persistence behavior; do not delete its
data files. Leave a shared PostgreSQL service running. Only if the native service
belongs solely to this stopped development session, use elevated PowerShell:

```powershell
Stop-Service -Name 'postgresql-x64-18'
deactivate
```

Do not uninstall software automatically, remove containers,
volumes or database files, or run queue purge commands.

## Troubleshooting and acceptance limits

| Symptom | Resolution |
| --- | --- |
| Missing SECRET_KEY | Configure ignored backend/.env; confirm the terminal settings module and stale environment overrides |
| Could not find GDAL / DLL load failure | Install matching 64-bit GIS libraries; use real DLL paths and dependencies; restart the process |
| Password authentication / wrong target | Check DATABASE_URL precedence, actual database/role/port; do not reset credentials/data blindly |
| PostGIS function/extension missing | Install matching server extension package; administrator enables it in the intended database |
| Permission denied creating test DB/extension | Dedicated CREATEDB test role and real DBA-provisioned PostGIS template |
| Redis refused/timed out | Native Memurai service/listener or hosted endpoint TLS/authentication; test all three URLs |
| Memurai stops after ten days | Developer edition uptime limit; stop clients and safely restart while preserving persistence |
| Jobs remain pending | Same broker URL, registered tasks, subscribed queue, native solo worker running, development module/eager disabled |
| Worker/control call hangs | Solo task may block all processing; inspect bounded I/O and logs; caller timeout is not task cancellation |
| Scheduled jobs absent | Exactly one Beat, correct timezone/database/broker; inspect schedule and logs |
| Media/report object errors | Configure private S3 service; unconfigured/memory adapters cannot provide durable cross-process storage |
| Frontend API errors | Django on 8000, Vite on strict 5173; existing proxy and CORS origin; port conflict must be resolved |

Current validation: Python compilation, dependency consistency (`pip check`),
isolated GIS setting/path/directory-handle checks, non-eager PostGIS configuration,
ten Beat entries and production GIS override isolation **passed** during the first
configuration update. Native Celery solo dispatch/retry/Beat tick smoke **passed**
in the follow-up, using private test-only memory transport. Native PostgreSQL
18.6 service/pg_isready verifies connection acceptance only. Updated checks are
recorded in the investigation follow-up. Django startup, migration inspection/drift
and full pytest are blocked by missing GDAL before domain-test execution.
PostgreSQL/PostGIS workflows, real Redis connectivity, Redis-backed Celery/Beat,
durable media and live email are **not verified**. No Redis data or queue was cleared.
No passing domain-test count is claimed. Production deployment and launch
acceptance remain governed by [M26 runbook](M26_PRODUCTION_RUNBOOK.md).
