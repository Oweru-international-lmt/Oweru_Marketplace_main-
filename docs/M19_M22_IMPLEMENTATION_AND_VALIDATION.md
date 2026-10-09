# M19 through M22 implementation and validation

Oweru Marketplace backend, baseline `a42aa1e` on `main`. Reviewable implementation with **1,587 passing PostgreSQL/PostGIS tests**; partial requirements and integrations are identified below. No commit or push. Authority and exact requirements are in [M19_M22_REQUIREMENTS_AND_PLAN.md](M19_M22_REQUIREMENTS_AND_PLAN.md).

## Baseline

Recreated isolated PostgreSQL/PostGIS environment because Docker Engine was available with zero containers/images. Complete unchanged suite: **1,499 passed in 198.42 seconds**. System check: zero issues. Migration drift: no changes detected. Commands run inside `oweru-m19-test-runner`, working directory `/workspace/backend`, using `--settings=config.settings.test_postgresql` or pytest `--ds=config.settings.test_postgresql`. No SQLite substitution.

## M19

Anonymous pin/category/size/description/phone submission, optional image evidence/external URL/email, normalized phone quota under PostgreSQL advisory locks, idempotent replay, outside canonical PropertyRecord and separate Oweru prospect record, frozen bilingual sanitized report, expiring HMAC capability and short-lived signed PDF access. No Full Check/Level 3 job is created. Outside submissions cannot be listed through the existing listing service without separate onboarding.

Endpoints: POST `/api/v1/free-checks/` (Idempotency-Key); GET `/api/v1/free-checks/{uuid}/?token=...`; GET `/api/v1/free-checks/{uuid}/pdf/?token=...`. Submission exposes self-service wa.me URL. Check history/evidence/report records have ORM and PostgreSQL immutability guards. Storage cleanup runs on failed transactions.

Focused PostgreSQL result: **256 passed in 32.40 seconds**, Free Check, canonical property and listing-service tests. Earlier intermediate focused run: 204 passed; the 256-test run adds provider/photo/database-guard coverage and listing integration. English/Swahili long-description PDF samples rendered with Poppler and every generated page visually inspected: one page each, no clipping or overlap. Samples are temporary QA artifacts.

FRC-02 limitation: no authoritative Tanzania land/coastline/description dataset or licensed imagery provider is supplied. Land/description responses explicitly say UNAVAILABLE by default. Adapter validation is tested; geography conclusions are not verified live. Photo mismatch uses uploaded file metadata and reports unavailable where metadata is missing. Duplicate proximity uses existing configured PostGIS radius; no matching private identifiers are exposed. Optional-email intent integrates in M21. FRC-03 screen buttons belong to the excluded frontend scope. FRC-04 forbids coordinates/boundaries in shared reports; description validation rejects explicit geometry terms/coordinate pairs rather than reflecting them into PDFs.

## M20

Anonymous WEB intake and authorized staff WHATSAPP/EMAIL intake share the desk. Categories and exact six SRD states, source-channel acknowledgement intent, working-day targets, status capability, private bounded evidence, append-only responses/history, handler assignment, verification escalation and Director-only final review. Changes require the current version. Final review can be requested after resolution/closure within 14 days, once. Staff detail/evidence rechecks active persisted permissions and object scope. Verifiers see only assigned verification complaints until escalation. Intake/history guards reject direct database rewrites/deletion.

Endpoints: POST `/api/v1/complaints/`; GET `/{uuid}/status/?token=...`; POST `/{uuid}/response/`, `/{uuid}/final-review/`. Management desk `/api/v1/management/complaints/`, `/{uuid}/`, `/{uuid}/evidence/{uuid}/`, and POST `/{uuid}/transition/`, `/{uuid}/assign/`, `/{uuid}/response/`.

Complaints serialize on the existing Deal lock before Complaint lock and write the existing PayoutBlock boundary. Open complaints hold existing payouts and block future payouts; multiple open complaints remain independent. Resolved/closed complaints clear their own block only; payout release remains an authorized financial action. Final review reopens the block. Paid payouts cannot be reversed by a complaint.

Final M20 focused PostgreSQL result: **70 passed in 45.30 seconds** (complaints plus payments). Earlier run: 66 passed in 48.95 seconds. Transition edges derive from the SRD lifecycle, whose text lists states but no exhaustive transition table. Working-day computation reuses the existing configurable holiday list. Director/Head of Operations designation is an explicit account field; no ordinary profile/role API accepts it. Trusted deployment setup remains necessary, and generic Management cannot perform final Director review. Complaint status capabilities have no invented expiry; revocation and retention policy remain unresolved. PostgreSQL guards protect referenced evidence media as well as immutable evidence records.

## M21

Central Notification rows use unique event/channel keys. Domain transactions persist durable intent and notifications together. Signals bridge existing VerificationNotice, FinancialNotice, ConfirmationDelivery, ComplaintNotice, FreeCheckReport, identity audit events and paid-payout transitions. `reconcile_notification_intents` idempotently imports earlier durable intents without sending messages. Existing confirmation tokens, expiry rules, financial snapshots and compatibility endpoints remain in use.

Channels: screen, email, staff outbox, self-service. SMS is rejected and workers send only email. WhatsApp remains manual click-to-chat plus mark-sent per NTF-05. Operational Management/Verifier/Marketer accounts need persisted outbox.send; optional grants/revocations are enforced. Manual send records one sender/audit under concurrency. Confirmation previews include frozen decision context; expired/consumed waiting links are omitted. Sent history retains rendered messages after consumption. Bilingual catalogue templates have safe placeholders, versions, immutable history, stale-write rejection and audit.

Account reset/verification retain their immediate email contract through the central adapter. Catalogue producers cover identity decisions, new leads, payment instructions, payout paid, owner confirmations/consent, tasks, professional setup, Full Check readiness, Free Check and complaints. Full Check report-ready channels are corrected to screen/email. Expiry tasks cover identity, normalized Full Check jobs and legacy property/location verification. Public contact-lister and relevant-lister buyer-payment self-service links construct messages without sending them.

SMTP tests use Django's in-memory mail backend. Delivery attempts record success/failure, redacted exception types, bounded exponential retries and a configurable maximum. Row locks prevent concurrent submission of the same row and Message-ID is stable. **External SMTP exactly-once delivery is not guaranteed across provider acceptance followed by process failure/database rollback.** No live SMTP receipt, provider deduplication or WhatsApp delivery was verified. Celery/Beat, production mail, private storage and absolute URLs need deployment configuration. Outbox working-hour highlighting skips weekends; staff shifts/holiday hours are unspecified.

OFFICIAL_REGISTRATION has a template but no producer: legacy M16 lacks invitation/pending approval state. Support-assisted WhatsApp password reset also has no producer; identity checks/support authority need policy before exposing that capability. Template availability is not event acceptance.

Focused M21 integration: **467 passed in 92.65s** (notifications, Free Check, complaints, verification, identity/accounts); outbox follow-up: **29 passed in 30.43s**. Final hardening across all four new apps: **88 passed in 33.29s**, including immutable referenced media, consumed-link sent history, legacy expiry reminders and Director fee approval. These runs overlap and must not be summed.

## M22

Management dashboard counts identity approvals, duplicate-related active flagged listings, Needs official tasks, payment proofs awaiting confirmation, due/held payouts, complaint statuses/overdue resolution and waiting outbox. Existing dedicated desks retain detail/actions. Partner approval returns available=false/count=null because legacy partner models lack a pending approval state. Capture/photo flags remain in existing capture services but are not aggregated into this dashboard badge.

Accounts require reason/current administration version, persisted permissions and ordered locks. Self-suspension/last active Management removal are blocked. Operational names are editable; client privilege/password overposting is rejected. Listing suspend/restore reuse existing authorization/activation eligibility, require reason and store actual reason in immutable restricted AdministrationHistory; the general listing audit retains reason_present to preserve its privacy contract. New listing actions compare updated_at for stale-write rejection. Existing approved-locality APIs implement ADM-03 and are regression-tested.

Staff provisioning is limited to Verifier/Marketer, assigns both existing role stores, uses an unusable initial password and emits an expiring secure setup link. Management designation is excluded from HTTP creation. Trusted command: `designate_management_office <email> DIRECTOR|HEAD_OPERATIONS --setup-actor <active-superuser-email> --reason <text>`. It requires an already-existing Management target and audits the change. No real user was designated during this work. Full Check fee changes require persisted Director designation; the fee remains unset until configured.

VerificationSetting now has validated database defaults, per-key PostgreSQL locks, versions and immutable SettingHistory. All section 22 scalar settings are exposed. Existing versioned commission tables/bands are reused and linked from settings; frozen financial calculations are not duplicated. Consumers are wired for identity/location validity, payout deadlines, duplicates, lost/sold review, confirmations, M17/M18 thresholds/deadlines and all new milestone settings. official_registration_days/public_map_rounding_m are stored/editable but have no legacy consumer: invitations are absent and current public APIs suppress exact geometry rather than round a point. Changes do not retroactively expire historical records.

Management history/audit reads are restricted and audited. PostgreSQL guards protect AdministrationHistory/SettingHistory. Tests cover seven non-management roles, inactive/revoked access, overposting, stale writes, rollback, settings/account races, raw history edits, staff setup and governance. M22 dependent regression: **571 passed in 124.82s**; post-correction domain regression: **469 passed in 98.39s**. All final changes are included in the complete suite below.

## Final validation and inventory

Complete final suite: **1,587 passed in 185.78s**, no failures/skips reported. An intermediate full run returned 1 failed/1,580 passed in 198.15s because the listing general audit included a sensitive reason; this was fixed by recording restricted reason history and preserving the existing audit contract. A misplaced test assertion was corrected before passing focused validation.

Final check/drift/diff results and full file inventory follow below. Temporary PDF-review PNGs and their empty folders were removed using verified workspace-contained paths. No frontend files, credentials, commit or push were introduced.

## API inventory

All paths have `/api/v1/` prefix; identifiers are UUIDs except listing IDs and setting/template keys.

| Methods | Path | Access |
|---|---|---|
| POST | `free-checks/` | Anonymous; Idempotency-Key; optional multipart photos |
| GET | `free-checks/{id}/`, `free-checks/{id}/pdf/` | Expiring token query parameter |
| POST | `complaints/` | Anonymous WEB / authorized staff EMAIL or WHATSAPP; optional evidence |
| GET | `complaints/{id}/status/` | Complaint token |
| POST | `complaints/{id}/response/`, `complaints/{id}/final-review/` | Token; bounded response or reason/window checks |
| GET | `management/complaints/`, `management/complaints/{id}/` | Management / assigned-verifier object scope |
| GET | `management/complaints/{id}/evidence/{evidence_id}/` | Object-authorized signed private evidence URL |
| POST | `management/complaints/{id}/transition/`, `.../assign/`, `.../response/` | Handler/position checks; version for transitions/assignment |
| GET | `notifications/` | Active user's own screen inbox |
| POST | `notifications/{id}/read/` | Own screen notification; empty body |
| GET | `notifications/self-service/listings/{listing_id}/` | Public-listing eligibility; language |
| GET | `notifications/self-service/deals/{id}/` | Relevant authorized lister; buyer payment instructions |
| GET | `management/notifications/outbox/` | Granted staff; history=1 for sent items |
| POST | `management/notifications/outbox/{id}/sent/` | Granted staff; empty body; idempotent marker |
| GET | `management/notifications/message-templates/` | Management settings permission |
| PUT | `management/notifications/message-templates/{key}/` | Management; en/sw/version |
| GET | `management/dashboard/`, `management/settings/` | Management |
| GET, PUT | `management/settings/{key}/` | Persisted history / validated value and current version |
| POST | `management/accounts/` | Management account.manage; Verifier/Marketer setup |
| GET, POST | `management/accounts/{id}/` | Authorized account/history read or reasoned versioned change |
| POST | `management/listing-actions/{listing_id}/` | Management; action/reason/updated_at version |
| GET | `management/audit/` | Management audit.view; bounded reader |
| PUT | `management/verification-settings/{key}/` | Existing compatibility route now requires/returns version; fee Director-only |

Existing listing restoration now requires a reason. Existing localities, financial, verification, authorization and commission APIs remain the reused domain boundaries. Capability responses for Free Check/complaints set no-store/no-referrer headers.

## Requirements acceptance matrix

| IDs | Actual coverage / limitation |
|---|---|
| FRC-01 | Backend input/photo validation implemented; frontend map/input UI excluded |
| FRC-02 | PostGIS duplicate/photo checks implemented; geography/description adapter tested, live provider unavailable |
| FRC-03 | Screen payload, PDF, expiry, self-service URL and optional email intent implemented; frontend/live receipt unverified |
| FRC-04 | Sanitized bilingual PDF tested and visually inspected; outside URL retained privately rather than shared |
| FRC-05, FRC-06 | Outside canonical record/prospect and configurable normalized-phone concurrent quota implemented |
| CMP-01, CMP-02 | Anonymous and staff intake/private evidence implemented; contextual prefill is frontend scope |
| CMP-03 | Number/channel-specific acknowledgement intent implemented; one-working-day human/provider delivery unverified |
| CMP-04, CMP-05 | Routing, position/object restrictions, valid lifecycle/history and status link implemented |
| CMP-06 | Current/future payout blocking, multiple holds and reopening tested |
| CMP-07, CMP-08 | Outcome/reasons, Director review window, deadlines/overdue resolution implemented; live outcome delivery unverified |
| NTF-01 | Central layer bridges existing intents; official invitation and support reset producers incomplete |
| NTF-02 | Authorized outbox/manual sending/history tested; weekday highlight calendar partial |
| NTF-03, NTF-04 | Self-service links/editable bilingual templates implemented; frontend activation excluded |
| NTF-05, NTF-06 | No SMS or automatic WhatsApp; creation/sent/email-attempt logging tested; live receipt unverified |
| NTF-07 | Email adapter boundary implemented; future automatic WhatsApp adapter is not an approved Phase 1 sender |
| ADM-01 | Supported queues implemented; pending partner approval unavailable; capture flags not aggregated |
| ADM-02, ADM-03 | Reasoned suspend/restore/concurrency and existing locality approval reused/tested |
| ADM-04 | Scalar settings/history and versioned commissions exposed; invitation/public-rounding consumers absent |
| ADM-05 | Existing immutable audit/new histories reused; restricted reads/rollback tested |

## Forward migrations

- `accounts/0008_user_management_position.py`: Director/Head of Operations distinction.
- `accounts/0009_user_administration_version.py`: stale-write protection.
- `properties/0003_propertyrecord_is_outside_check_and_more.py`: explicit anonymous outside records and canonical-context constraint.
- `free_checks/0001_initial.py`, `0002_immutable_history.py`, `0003_report_media_guards.py`: checks/prospects/photos/reports and immutable referenced media.
- `complaints/0001_initial.py`, `0002_history_guards.py`, `0003_evidence_media_guards.py`: lifecycle/evidence/responses/notices, history/intake/state guards and media protection.
- `notifications/0001_initial.py`, `0002_history_guards.py`: messages/templates/attempts and immutable delivery/template history.
- `verification/0010_verificationsetting_version_settinghistory.py`: setting versions/history.
- `administration/0001_initial.py`, `0002_history_guards.py`: management history and administration/setting history guards.

Tests create the database from the forward migration graph. SQL guards are PostgreSQL-specific and were exercised on PostgreSQL. No migration was applied to production. Historical expiry dates are retained.

## Remaining integrations and unresolved policies

1. Supply/licence authoritative Tanzania land/coastline/description data and imagery, configure the geography provider and verify real outputs. UNAVAILABLE is deliberate partial acceptance.
2. Configure production Marketplace/confirmation/setup URLs, SMTP, Celery/Beat, private storage and staff WhatsApp operation. Tests prove adapter behavior, not provider receipts or encryption at rest.
3. Establish Director/Head of Operations through trusted setup; approve the Full Check fee and define holiday/shift/SLA operations. No production fee or privileged user was invented.
4. Extend approved legacy partner onboarding with invitation/pending approval state before claiming OFFICIAL_REGISTRATION/partner queue acceptance. Define support-assisted password-reset identity checks/authority.
5. An approved coarse-map consumer is needed for the rounding setting; current public APIs keep exact geometry private. Dashboard aggregation of capture flags remains incomplete.
6. Decide complaint status-capability revocation/retention and acknowledgement monitoring. Legacy and central outboxes coexist for compatibility; reconciliation sends nothing.

These partial requirements prevent claiming complete production acceptance of every M19-M22 requirement.

## Final checks and full changed-file inventory

Django system check: zero issues. Migration drift: no changes detected. Complete PostgreSQL/PostGIS suite: **1,587 passed in 185.78s**. `git diff --check`: passed. `git diff --stat` inspected: tracked integrations total 21 files, 156 insertions, 56 deletions; Git omits untracked app/document additions from that statistic.

Full inventory: **84 files** (21 modified tracked, 63 new untracked). All files are backend or documentation. No staged changes, frontend edits, secrets matching the reviewed credential/private-key patterns, or temporary QA artifacts. Branch remains main, HEAD a42aa1e. No commit or push. Container-only dependencies/test databases are not repository artifacts.

| Status | File |
|---|---|
| Modified | `backend/apps/accounts/email_verification.py` |
| New | `backend/apps/accounts/migrations/0008_user_management_position.py` |
| New | `backend/apps/accounts/migrations/0009_user_administration_version.py` |
| Modified | `backend/apps/accounts/models.py` |
| Modified | `backend/apps/accounts/reset_services.py` |
| New | `backend/apps/administration/__init__.py` |
| New | `backend/apps/administration/api.py` |
| New | `backend/apps/administration/apps.py` |
| New | `backend/apps/administration/management/__init__.py` |
| New | `backend/apps/administration/management/commands/__init__.py` |
| New | `backend/apps/administration/management/commands/designate_management_office.py` |
| New | `backend/apps/administration/migrations/0001_initial.py` |
| New | `backend/apps/administration/migrations/0002_history_guards.py` |
| New | `backend/apps/administration/migrations/__init__.py` |
| New | `backend/apps/administration/models.py` |
| New | `backend/apps/administration/services.py` |
| New | `backend/apps/administration/tests/__init__.py` |
| New | `backend/apps/administration/tests/test_management.py` |
| New | `backend/apps/administration/urls.py` |
| New | `backend/apps/complaints/__init__.py` |
| New | `backend/apps/complaints/api.py` |
| New | `backend/apps/complaints/apps.py` |
| New | `backend/apps/complaints/migrations/0001_initial.py` |
| New | `backend/apps/complaints/migrations/0002_history_guards.py` |
| New | `backend/apps/complaints/migrations/0003_evidence_media_guards.py` |
| New | `backend/apps/complaints/migrations/__init__.py` |
| New | `backend/apps/complaints/models.py` |
| New | `backend/apps/complaints/services.py` |
| New | `backend/apps/complaints/tests/__init__.py` |
| New | `backend/apps/complaints/tests/test_complaints.py` |
| New | `backend/apps/complaints/tests/test_payout_integration.py` |
| New | `backend/apps/complaints/urls.py` |
| New | `backend/apps/free_checks/__init__.py` |
| New | `backend/apps/free_checks/api.py` |
| New | `backend/apps/free_checks/apps.py` |
| New | `backend/apps/free_checks/migrations/0001_initial.py` |
| New | `backend/apps/free_checks/migrations/0002_immutable_history.py` |
| New | `backend/apps/free_checks/migrations/0003_report_media_guards.py` |
| New | `backend/apps/free_checks/migrations/__init__.py` |
| New | `backend/apps/free_checks/models.py` |
| New | `backend/apps/free_checks/services.py` |
| New | `backend/apps/free_checks/tests/__init__.py` |
| New | `backend/apps/free_checks/tests/test_free_checks.py` |
| New | `backend/apps/free_checks/texts.py` |
| New | `backend/apps/free_checks/urls.py` |
| Modified | `backend/apps/leads/services.py` |
| Modified | `backend/apps/lister_identity/services.py` |
| Modified | `backend/apps/listings/services.py` |
| Modified | `backend/apps/listings/views.py` |
| New | `backend/apps/notifications/__init__.py` |
| New | `backend/apps/notifications/api.py` |
| New | `backend/apps/notifications/apps.py` |
| New | `backend/apps/notifications/catalog.py` |
| New | `backend/apps/notifications/management/__init__.py` |
| New | `backend/apps/notifications/management/commands/__init__.py` |
| New | `backend/apps/notifications/management/commands/reconcile_notification_intents.py` |
| New | `backend/apps/notifications/migrations/0001_initial.py` |
| New | `backend/apps/notifications/migrations/0002_history_guards.py` |
| New | `backend/apps/notifications/migrations/__init__.py` |
| New | `backend/apps/notifications/models.py` |
| New | `backend/apps/notifications/services.py` |
| New | `backend/apps/notifications/signals.py` |
| New | `backend/apps/notifications/tasks.py` |
| New | `backend/apps/notifications/tests/__init__.py` |
| New | `backend/apps/notifications/tests/test_notifications.py` |
| New | `backend/apps/notifications/urls.py` |
| Modified | `backend/apps/payments/confirmations.py` |
| Modified | `backend/apps/payments/services.py` |
| Modified | `backend/apps/properties/duplicate_services.py` |
| New | `backend/apps/properties/migrations/0003_propertyrecord_is_outside_check_and_more.py` |
| Modified | `backend/apps/properties/models.py` |
| Modified | `backend/apps/verification/configuration.py` |
| Modified | `backend/apps/verification/full_check_api.py` |
| Modified | `backend/apps/verification/full_check_services.py` |
| Modified | `backend/apps/verification/job_models.py` |
| New | `backend/apps/verification/migrations/0010_verificationsetting_version_settinghistory.py` |
| Modified | `backend/apps/verification/models.py` |
| Modified | `backend/apps/verification/services.py` |
| Modified | `backend/apps/verification/tests/test_full_check.py` |
| Modified | `backend/apps/verification/tests/test_full_check_invariants.py` |
| Modified | `backend/config/api_urls.py` |
| Modified | `backend/config/settings/base.py` |
| New | `docs/M19_M22_IMPLEMENTATION_AND_VALIDATION.md` |
| New | `docs/M19_M22_REQUIREMENTS_AND_PLAN.md` |
