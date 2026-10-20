# Oweru Marketplace: architecture

How the Phase 1 web system is built, how the parts talk to each other, and how far each SRD module has got. For the short version, read [architecture-essentials.md](architecture-essentials.md). For what to build, read [srd.md](srd.md).

Last checked against the code: 21 October 2026, `main` at `9d1215c`.

## 1. System at a glance

One React single-page app serves every kind of user. It talks to one versioned Django REST API. The API owns every business rule and every permission check; the browser only decides what to show.

```
 Browser (phone or computer)
   React 19 SPA  ── /api/v1 (JSON, JWT) ──►  Django 5.2 + DRF
   Vite dev server proxies /api in dev       │
                                             ├── PostgreSQL + PostGIS   (all records, geometry)
                                             ├── Redis                  (cache, Celery broker)
                                             ├── Celery worker + beat   (email, expiry, deadlines, aggregates)
                                             ├── Private S3 storage     (photos, documents, reports; signed links)
                                             └── ReportLab              (free check and full check PDFs)

 People outside the app:
   Staff WhatsApp outbox ── wa.me click-to-chat ──► owners, officials, professionals, complainants
   Self-service buttons  ── wa.me click-to-chat ──► the user's own WhatsApp
   SMTP email (automatic)
```

Phase 1 limits that shape everything (SRD 2.4):

- No SMS anywhere. WhatsApp is never sent automatically: the system prepares the message and a person presses send.
- Money moves by bank transfer outside the system. The system records amounts, slips, confirmations and payouts; it never moves money.
- The database starts empty. Every feature must work with no data and grow with use.
- No word "guarantee" in the interface.

## 2. Repository layout

```
backend/                 Django project (build context for the production image)
  config/                settings (base, development, test, test_postgresql, production), urls, celery
  apps/                  one Django app per domain (section 4)
  tests/core/            foundation, deployment and performance tests
  scripts/               Windows Celery smoke test
frontend/                React app (Vite, TypeScript, Tailwind v4)
  src/pages/             screens, grouped by audience: public/, lister/, staff/, account/
  src/lib/               API clients (one *Api.ts per area), formatting, tokens
  src/components/        shared UI
  src/layouts/           PublicLayout, AuthLayout, AppLayout + Sidebar, navigation.ts
  src/i18n/              sw.ts (default) and en.ts
docs/                    this documentation set, milestone reports, runbooks
docker/, docker-compose*.yml   production containers (web, worker, beat, release) and dev db/redis
```

`backend/accounts`, `audit`, `authorization` and `core` at the top level are ignored leftovers from an earlier layout. The live code is under `backend/apps/`.

## 3. Technology

| Layer | Choice | Notes |
|---|---|---|
| API | Django 5.2, Django REST Framework 3.16 | URL path versioning, only `v1` |
| Auth | SimpleJWT | Access 15 minutes, refresh 7 days, rotated and blacklisted on use |
| Database | PostgreSQL with PostGIS (GeoDjango) | Points, boundaries, distances, overlap and area |
| Jobs | Celery 5 with Redis | 10 scheduled tasks (section 7) |
| Files | Private object storage via `apps.media.storage` | Backends: `s3` (boto3), `memory`, `unconfigured` |
| PDF | ReportLab | Free check report, full check report |
| API docs | drf-spectacular | `/api/v1/schema/`, `/api/v1/docs/`, `/api/v1/redoc/` |
| Tests | pytest, pytest-django | Default settings `config.settings.test_postgresql` |
| Web app | React 19, TypeScript 6, Vite 8 | Single-page app, React Router 7 |
| Styling | Tailwind CSS 4 | Brand tokens in `frontend/src/index.css` (see [design.md](design.md)) |
| Motion | `motion/react` for component state, GSAP with `useGSAP` for page sequences | Both respect reduced motion |
| Maps | Leaflet | OpenStreetMap tiles in development, Esri World Imagery for satellite views in staff screens; provider to be contracted (SRD 2.6) |
| i18n | i18next | Swahili default, English second |
| Lint | oxlint | Includes React hooks, purity and only-export-components rules |

## 4. Backend domains

Every app follows the same shape: `models.py`, `services.py` (business rules), `api.py` or `views.py` (thin HTTP layer), `serializers.py`, `urls.py`, `tests/`. Some large apps split services by workflow (for example `verification/full_check_services.py`, `verification/review_desk.py`).

| App | SRD module | Owns |
|---|---|---|
| `accounts` | 5.1 ACC | Custom `User` (email sign-in, unique phone), registration, login lockout, password reset, email confirmation, profile, deletion request |
| `roles` (+ `legacy_authorization`) | 4 | Canonical roles (buyer, owner, agent, local_official, professional, verifier, marketer, management), permission catalog, role assignment, outbox-send grants |
| `audit` | ADM-05, NFR-04/05 | Append-only `AuditLog`; `create_audit_log`, `record_sensitive_access` |
| `common` | | Base models (`UUIDModel`, `TimeStampedModel`, `CreatedByModel`), health checks, JSON logging, request observability |
| `localities` | LST-03, ADM-03 | Region, district, ward, street or village; proposed localities and approval |
| `lister_identity` | 5.2 IDV | National ID, ID photo, live selfie, review, expiry, public lister profile |
| `properties` | LST-01, LST-12 | `PropertyRecord` and Property ID, possible duplicates and their review |
| `listings` | 6 LST, 7 SRC | Listings, status machine, photos, public search and property page, management suspend and restore |
| `media` | LST-13, NFR-04 | Private uploads, content validation, signed access links |
| `leads` | 8 LEAD | Leads, stage transitions, notes, follow-ups, customer list, performance metrics |
| `deals` | 8, 9 | Deal created at Closing |
| `commissions` | 9.3 PAY-01/02 | Versioned rate tables, publishing, frozen calculations |
| `payments` | 9 PAY | Bank accounts, owner confirmations (`confirmations.py`), payment instructions, slips, receipt confirmation, tax receipts, payouts and holds, idempotency |
| `verification` | 10 LVL, 11 VER, 12 FUL | Level calculation and snapshots, location check (document review desk, title documents, field review), verification tasks, full check jobs, results, reports, settings (`configuration.py`) |
| `site_capture` | 13 MAP | Capture sessions, corner points with accuracy, media with EXIF, boundaries, public map layers |
| `local_officials` | 14 LOC | Officials, jurisdictions, coverage, routing |
| `professionals` | 15 PRO | Professional profiles, eligibility by type and district |
| `free_checks` | 16 FRC | Public check, verdicts, PDF, daily limit, outside Property Record |
| `complaints` | 17 CMP | Intake, routing, statuses, evidence, responses, final review, payout hold |
| `analytics` | 18 MON | Anonymous events, nightly aggregates, panel and Excel export |
| `marketing` | 19 MAR | Featured listings, banners and content pages, email campaigns, source tags, consent |
| `notifications` | 20 NTF | Central messaging layer, message catalogue and templates, outbox, email delivery, self-service links |
| `administration` | 21 ADM | Management dashboard queues, settings API, account administration, audit view |

## 5. Cross-cutting rules in the backend

These patterns repeat everywhere. New code should use them rather than invent new ones.

### 5.1 Permissions

- Default DRF permission is `IsAuthenticated`. Public endpoints opt out explicitly with `AllowAny` and their own throttles.
- Services check permissions themselves with `apps.leads.policies.authorize(actor, "<permission>")`, which re-reads the user, requires an active account and checks the permission catalog. `management(actor)` checks for operational Management.
- Object scope is a second check: a lister only sees their own leads (`lead_scope`), a partner only their own tasks, and so on.
- The frontend hides what a user cannot use, but that is never the security boundary.

### 5.2 Audit and sensitive access

- Every staff or partner action and every status change writes `create_audit_log(actor, action, entity_type, entity_id, before, after, request)`.
- Every read of identity, bank, payment or private verification data writes `record_sensitive_access(...)`.
- Audit rows are append-only. There is no update or delete path.

### 5.3 Idempotency and concurrency

- Money, orders and uploads require an `Idempotency-Key` header. `apps.payments.idempotency.execute(...)` locks the resource, runs authorization, then either replays the stored result or runs the mutation once. Reusing a key with a different payload returns 409.
- Editable records carry a `version`. Writes send the version they read; a mismatch returns 409 and the client reloads.
- PostgreSQL advisory locks protect counters and limits (for example the free check daily limit and setting changes).

### 5.4 Settings

- Configurable values from SRD 22 live in `apps.verification.configuration`: `DEFAULTS`, `setting(key)` and `change_setting(...)` with history and audit. Some defaults come from environment variables (`ENV_DEFAULTS`).
- Never hard-code a threshold, expiry or fee. Read it with `setting(...)`.
- The full check fee needs the Director. The full check scope has an English and a Swahili value (`full_check_scope`, `full_check_scope_sw`), both frozen into each order.

### 5.5 Records are never deleted

- Property Records, evidence, submissions, deals, payments and audit rows are kept for life. Corrections are new versions.
- Several tables have database triggers that block changes to frozen fields (for example a full check job's scope and subject snapshots).

### 5.6 Notifications

- Domain apps never send email or WhatsApp themselves. They create a domain notice row (for example `ComplaintNotice`, `VerificationNotice`, `FinancialNotice`, `ConfirmationDelivery`). Signals in `apps/notifications/signals.py` turn each notice into central `Notification` rows through `emit(...)`.
- Channels: `screen`, `email` (delivered by Celery with retries), `outbox` (staff WhatsApp), `self_service` (wa.me link for the user).
- Message text comes from the catalogue in `notifications/catalog.py`, overridable as bilingual templates. Text is rendered in the recipient's language.
- Links in messages must point to frontend pages built from `MARKETPLACE_PUBLIC_URL` (for example `/complaints/<id>?token=...`), never to `/api/v1/...`.
- The outbox screen (`/management/notifications/outbox/`) gives staff the message, the recipient and a wa.me link. Mark as sent is recorded with the sender.

### 5.7 Confirmation links

- Owners and partners confirm things without an account through single-use links: `OWNER_CONFIRMATION_URL` (the frontend `/confirm` page) with a delivery id and token.
- Purposes: `PHONE`, `OWNER_PRICE`, `OWNER_RECEIPT` (answered at `/payments/confirmations/<id>/`) and `FULL_CHECK_CONSENT` (answered at `/full-checks/consent/<id>/`).
- The page shows what is being agreed (`details`): property, area, price, agent. It never shows the buyer. The decision, time, IP and browser are stored.

### 5.8 Files

- All uploads are private. The API returns short-lived signed links (`/media/<id>/access/` and per-domain evidence endpoints).
- Uploads are validated by content, not only by extension: images for photos, PDF or image for documents, with size limits.
- Photos are resized for display; originals are kept privately as evidence (LST-13).

### 5.9 Verification level

- The level is calculated, never set: `verification/services.py` annotates listings with the effective level from current checks. `verification/levels.py` keeps a snapshot cache, refreshed on events and nightly.
- Level wording is fixed (SRD 10). Level 3 wording and badge style are reserved.

### 5.10 Throttling

Signed-in users: 1,200 requests per hour. Sign-in 10 per minute, registration 5 per hour, token refresh 30 per minute, confirmations 20 per hour. Public search and property pages have no blanket anonymous limit; public forms (free check, complaints) apply their own.

## 6. API conventions

- Base path `/api/v1/`. Public listing reads are under `/public/`; staff tools under `/management/`.
- Errors follow DRF: `{"detail": "..."}` or `{"field": ["..."]}`. A bare service `ValidationError("...")` arrives as `["..."]`. The frontend `ApiError` handles all three.
- 401 means sign in again (the client refreshes once and retries), 403 a missing permission, 404 also hides objects the user may not know exist, 409 an idempotency or version conflict, 429 a throttle with a wait time in the message.
- There is no global pagination setting. Views whose lists can grow set their own and return `{count, next, previous, results}`; others return a plain array. Check the endpoint before assuming either shape.
- Owner details, bank details, exact pins and private verification data never appear in public serializers.

## 7. Background jobs (Celery beat)

| Task | When | Purpose |
|---|---|---|
| `lister_identity.tasks.process_lister_identity_expiry` | 00:00 daily | Expire identities (IDV-04) |
| `verification.tasks.process_document_verification_expiry` | 00:15 daily | Expire location checks (VER-05) |
| `verification.tasks.recalculate_verification_levels` | 00:30 daily | Refresh level snapshots (LVL-01) |
| `payments.tasks.lost_sold_review` | 01:00 daily | Lost then sold review (LEAD-08) |
| `analytics.tasks.refresh_market_aggregates` | 02:00 daily | Market panel aggregates (MON-04) |
| `notifications.tasks.verification_expiry_reminders` | 08:00 daily | Reminders 30 days before expiry |
| `payments.tasks.payout_due_check` | every 15 minutes | Payouts that became due (PAY-10) |
| `verification.tasks.process_full_check_deadlines` | every 15 minutes | Consent, contact and task deadlines (FUL-02, LOC-05) |
| `notifications.tasks.deliver_pending_email` | every minute | Email delivery with retries (NTF-06) |
| `marketing.tasks.deliver_campaigns` | every minute | Campaign email delivery (MAR-03) |

## 8. Frontend architecture

### 8.1 Routing and layouts

- `src/App.tsx` holds every route. Three layouts:
  - `PublicLayout`: public site header, footer and bottom bar on phones. Home, search, property page, free check, complaints, confirmation links, full check order and status.
  - `AuthLayout`: split photo panel for sign in, sign up and password pages.
  - `AppLayout`: navy sidebar plus top bar for signed-in work: account, lister area, staff desks, management.
- Guards in `src/auth/guards.tsx`: `RequireAuth`, `GuestOnly`, `RequirePermission permission="..."`.
- `src/layouts/navigation.ts` is the single list of sidebar items. Each item names the permission that shows it.

### 8.2 Data access

- `src/lib/api.ts` `request<T>(path, {method, body, auth, headers})` is the only fetch wrapper. It adds the JWT, refreshes once on 401 with a shared promise (refresh tokens rotate), and throws `ApiError`.
- Each area has a client module: `authApi`, `listerApi`, `marketApi`, `servicesApi` (free check, complaints, full checks), `staffApi`, `panelApi`, `managementApi`, `confirmApi`. Pages call these, never `fetch` directly.
- `idempotencyKey()` makes one key per user action. Pass it as `Idempotency-Key` on orders, uploads and money actions.
- No global data library. Pages load with `useEffect` plus local state; keep `setState` calls in handlers and async callbacks, not synchronously in the effect body (lint rule).

### 8.3 Access in the UI

- `/auth/me/` does not return roles or permissions yet. `loadAccess()` in `src/lib/authApi.ts` probes a few endpoints and infers them (Management grants, the complaints desk, lister identity, marketing). This is a stopgap; replace it once `/auth/me/` reports roles.
- `can(user, permission)` and `hasRole(user, role)` decide what is shown. The API decides what is allowed.

### 8.4 Language

- Every visible string comes from `src/i18n/sw.ts` and `en.ts`. Swahili is the default and the fallback; the two files must have the same keys. Use `_one` and `_other` for plurals.
- The UI follows the visitor's choice and switches to the account's saved language at sign-in. Content that comes from the API in both languages (for example the full check scope) is picked by `i18n.language`.

### 8.5 Maps and location

- Leaflet. `MapPicker` for pins, `CheckMap` for the staff location check (satellite and street), `ListingsMap` for the lister's map, an SVG regions map (`/geo/tz-regions.json`, geoBoundaries ADM1, CC BY 4.0) on the market panel.
- Public maps show approximate positions only (SRC-02). Exact pins and boundaries stay in staff screens.

## 9. Environments

| Environment | Database | How to run | Notes |
|---|---|---|---|
| Development (native Windows) | PostgreSQL 18 + PostGIS, Memurai (Redis) | [NON_DOCKER_LOCAL_DEVELOPMENT.md](NON_DOCKER_LOCAL_DEVELOPMENT.md) | `config.settings.development`; Django on 127.0.0.1:8000, Vite on 5173 (fixed, other URLs point to it) |
| Tests | Disposable PostgreSQL/PostGIS | `pytest` from `backend/` | Default `config.settings.test_postgresql`, eager Celery, in-memory cache |
| Local preview (one machine only) | SpatiaLite file | `config.settings.local_preview` | Not in git (excluded in `.git/info/exclude`). In-memory uploads, preview photos served from outside the repo. PostgreSQL-only features (advisory locks, geography area, triggers) fail here, so tests that need them fail too |
| Production | PostgreSQL + PostGIS, Redis, S3 | `docker-compose.production.yml` (`web`, `worker`, `beat`, `release`) | [M26_PRODUCTION_RUNBOOK.md](M26_PRODUCTION_RUNBOOK.md); `production_preflight` validates settings; HTTPS only |

Key settings: `MARKETPLACE_PUBLIC_URL`, `PASSWORD_RESET_URL`, `EMAIL_VERIFICATION_URL`, `OWNER_CONFIRMATION_URL` (all frontend URLs), `CORS_ALLOWED_ORIGINS`, `MEDIA_STORAGE_*`, `EMAIL_*`, `REDIS_URL`, `CELERY_*`.

## 10. Status by module

What the backend provides and what the frontend uses, as of the date at the top. "API only" means the endpoints exist and are tested but no screen uses them yet.

| SRD module | Backend | Frontend screens | Status |
|---|---|---|---|
| 5 Accounts (ACC) | Done | Sign up, sign in, reset, email confirmation, account page, staff accounts and roles | Done. `/auth/me/` still lacks roles (8.3) |
| 5.2 Lister identity (IDV) | Done | Identity submission with live selfie; management review | Done, except the public lister profile (IDV-06): API only |
| 6 Listings (LST) | Done except bulk import | Listing editor with owner price and photos, my listings, lister home | LST-09 payout preview missing; LST-11 bulk import not built in the backend; duplicates queue (LST-12) and locality approval (LST-03) API only |
| 7 Search (SRC) | Done | Home, search with filters, property page, featured area | Done |
| 8 Leads and deals (LEAD) | Done | Lister enquiries pipeline and metrics | Lead notes and customer list (LEAD-06) API only; deal screens missing (LEAD-03 to 05) |
| 9 Payments (PAY) | Done | Owner price and money received confirmation links | Deal page, payment instructions and slips, management confirmation, tax receipts, payouts and holds, bank account and rate tables: API only |
| 10 Levels (LVL) | Done | Verification badge and panel on public pages | Done |
| 11 Verification jobs (VER) | Done | Location check: lister request with title documents, staff desk with map and checklist | Field verification review and task endpoints: API only |
| 12 Full check (FUL) | Done | Buyer order, payment and report; staff payment, verifier and result; owner consent link | In-app owner consent, owner contact, start, refresh, professional assignment: API only |
| 13 Site capture (MAP) | Done | None | API only |
| 14 Local officials (LOC) | Done | None | Registration, dashboard, task detail, management and coverage map: API only |
| 15 Professionals (PRO) | Done | None | API only |
| 16 Free check (FRC) | Done | Free check and result with PDF | Done |
| 17 Complaints (CMP) | Done | Lodge, status page with reply and final review; staff desk and detail | Done |
| 18 Market panel (MON) | Done | Market panel with filters, charts, regions map, Excel export | Done |
| 19 Marketing (MAR) | Done | Campaigns, composer, featured, content pages | Marketing emails link to an API consent address; check it opens a usable page |
| 20 Notifications (NTF) | Done | WhatsApp outbox; notifications list | Message template editor (NTF-04) and mark-as-read: API only |
| 21 Administration (ADM) | Done | Overview (complaints and full checks only) | Dashboard queues (ADM-01), settings (ADM-04), audit log, listing suspend and restore (ADM-02): API only |

The remaining work, its order, flows and finish lines are in [roadmap.md](roadmap.md).

## 11. Known technical debt

- `/auth/me/` should return roles, permissions and account category so the frontend can drop `loadAccess()` probes.
- The complaint intake response `status_link` points at the API status endpoint; the frontend only reads the token from it.
- Permissions are still stored by the `legacy_authorization` app while roles have moved to `apps.roles`.
- Older full check jobs have an English-only `scope_snapshot`; the UI falls back to English for them.
- The frontend README describes only the early screens; this document is the current map.

## 12. Further reading

- [srd.md](srd.md), [prd.md](prd.md): requirements.
- [design.md](design.md): visual system and screen patterns.
- [backend_authorization/BACKEND_AUTHORIZATION.md](backend_authorization/BACKEND_AUTHORIZATION.md): permission catalog and matrix.
- [M10_M13_BACKEND.md](M10_M13_BACKEND.md): leads, deals, commission, payments and payouts contracts.
- Milestone reports `M14` to `M26`: what each backend milestone delivered and its validation limits.
