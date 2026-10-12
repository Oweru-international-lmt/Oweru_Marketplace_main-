# M23–M26 backend requirements and plan

Baseline: main at `26fde45600092b89605f3ef8ce10a1e96b01e70e`. Frontend is strictly read-only. No commit, push, or deployment is authorized.

Authority: SRD v1.3 sections 4, 18, 19, 23 and 26; Backend Development Guide v1.1 sections 37–45, roadmap 46, definition of done 47 and implementation rule 52. SRD business rules take precedence.

## Repository investigation

The backend is a Django 5.2 modular monolith using PostgreSQL/PostGIS, UUID entities, private media storage, JWT, Redis, Celery and two compatible role stores. Persisted permission-bearing assignments control actions; canonical assignments alone do not establish an action grant. Existing domain services own listing visibility, verification levels, financial snapshots, immutable evidence, complaint payout blocks and notification delivery. Marketing and analytics permissions already exist. Public search/view events currently log safe metadata only; no durable analytics store or marketing consent exists.

Recent backend commits since M19–M22: `d02a360` removes blanket anonymous browsing limits, `3dd7fd3` accepts JSON pin text in multipart Free Check intake, `61f5ab8` preserves per-address throttles on public complaint/Free Check submissions, and `edd5637` adds complainant/type/date desk fields. Preserve these behaviors and all received frontend files.

## Sequential implementation

1. Establish a fresh full PostgreSQL/PostGIS suite, system check and migration drift check before application edits. Existing isolated M19 containers are reused, with a newly created pytest database; no keepdb.
2. M23: dated featured selections, bounded bilingual banners/pages, persisted opt-in/withdrawal, consent-filtered email campaigns and source-tagged links. Reuse active permissions, audit transactions and private listing visibility. No automatic WhatsApp or external delivery during verification.
3. M24: durable non-personal search/view/source events, aggregate monitoring with date/region/district/category filters, safe Excel export and nightly refresh. Use existing leads/transitions/deals/checks/partner coverage. Explicitly identify unavailable historical activation/source data; do not infer missing history as fact.
4. M25: production configuration validation, scoped rate limits, request observability, query/index verification and operational monitoring. Preserve public browsing behavior. Infrastructure encryption, network latency and uptime require operator evidence.
5. M26: reviewable backend deployment configuration and runbooks for migrations, workers/Beat, readiness, daily backups retained 30 days, replicated private storage and quarterly restore tests. Do not deploy.

## Acceptance

MAR-01–04: only Marketer/Management operate marketing; scheduled eligibility; both languages; campaigns select only active consenting users and recheck consent at delivery; delivery/click results; validated source tags. MON-01–04: required metrics, bounded filters, Excel export, no buyer/owner personal data, pre-calculated heavy metrics. NFR-01/03–08: authorization/privacy regressions, production checks, performance evidence, backups/recovery and monitoring. NFR-02/09–11 include frontend and provider responsibilities excluded from this backend-only change.

Run focused PostgreSQL tests after each milestone and the complete suite at completion. Check migrations, Django configuration, `git diff --check`, tracked changes and all untracked files. Explicitly assert both inventories contain no `frontend/` paths. Document actual results and unresolved launch dependencies without claiming live acceptance.
