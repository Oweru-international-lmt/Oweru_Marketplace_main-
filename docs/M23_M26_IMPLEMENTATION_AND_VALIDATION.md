# M23–M26 implementation and validation

Backend development is based on clean `main` at `26fde45600092b89605f3ef8ce10a1e96b01e70e`. No commit, push or deployment is authorized. Frontend files are preserved as received. Authority, recent backend commit effects and sequence are recorded in [the requirements and plan](M23_M26_REQUIREMENTS_AND_PLAN.md).

## Fresh regression baseline

The existing isolated PostgreSQL/PostGIS containers were restarted after Docker Engine startup. The full unchanged suite at `26fde45` passed **1,592 tests in 317.82 seconds**. Django system check reported zero issues and migration drift reported no changes. Tests create a fresh database; no SQLite or keepdb substitution was used. No production data was accessed.

## M23 Marketing

Scheduled featured selections require an eligible public listing and Marketer/Management permissions. Banners/pages carry bounded plain-text Swahili/English titles and bodies, local target paths, source tags, active periods, enabled state and optimistic versions. Writes and audit are atomic. Public content uses Swahili by default and current listing visibility; generated listing links match the received `/listings/:listingId` route. Unapproved guarantee wording is rejected; enabling approved wording requires a separate governed content policy integration.

Marketing consent defaults to false, is controlled by the authenticated account and creates versioned immutable history. User locks serialize first consent, withdrawal and delivery. Campaign creation selects only active opted-in accounts; workers recheck persisted active/consent state immediately before provider submission. Campaign bodies remain immutable. The existing central SMTP adapter owns provider submission. Retries are bounded, error text is redacted, Message-ID is stable, and concurrent workers submit once under row locks. Signed click capabilities expire after 30 days, return only a validated local redirect and count the first click. Results expose campaign counts without recipients' personal details. No SMS or automatic WhatsApp is introduced.

Initial focused PostgreSQL validation: **20 passed**. Subsequent integration and concurrency tests include these cases; overlapping runs must not be summed. Tests use an in-memory email backend or mocked adapter, never real campaigns. Provider receipt, spam/unsubscribe operations and SMTP exactly-once delivery across provider acceptance followed by process failure remain operational limitations. The received frontend has no marketing preference/content staff UI; backend consent APIs and email preference links require an approved consumer before real campaigns.

## M24 Analytics

Durable facts store only event type, administrative area IDs, category, coarse price bands, filter names and bounded source tag. No buyer/owner name, phone, email, IP, user agent, exact coordinates, bank detail, storage key or request payload is persisted in MarketEvent. Search/view recording fails open for browsing; enquiry attribution participates in the existing domain transaction. Leads retain their existing interest-source enum, with an optional separate `source_tag`. New closing transactions freeze listed-price snapshots without changing financial calculations. Existing audit activation timestamps supply timing where available.

Nightly materialized daily cells cover Active/Under offer inventory, mean/median selling prices, converted price per square metre, verification counts/shares, active listers/listings per lister, new listers by first listing, listing creation, demand/filter/price-band/source counts, enquiry cohorts/conversion, response and activation timing, won-deal value/discount, Free Check verdicts/mismatches and active official/professional coverage. Monthly price cells combine observed daily active-inventory samples, with observed-day count and explicit time weighting. Repeated nightly execution replaces aggregate cells atomically; permanent facts/history remain immutable. A separate command allows explicit refresh without sending messages.

Panel and Excel exports accept bounded date range, region, district, category and kind (`STOCK`, `ACTIVITY`, `COVERAGE`, `MONTHLY`). Both read precomputed cells, return at most 10,000 rows and recheck persisted staff grants. Monthly views use full calendar months; other kinds retain exact date boundaries. Excel uses inline string cells so source/content values cannot become formulas. Export rows include metric names and nested metric JSON; no personal identities are exported. Stale/uninitialized aggregates are explicit. Area heat counts can join approved administrative map layers; geographic polygons/centroids are not invented.

Metrics have explicit limits: stock/coverage history starts with actual snapshots; historic activation/discount data is null where missing; unknown-area searches and pin-only outside Free Checks remain unknown-area; conversion is enquiry-date cohorts with outcomes known at refresh, not a promise of future conversion; caller-supplied source tags are attribution rather than verified identity. Coverage measures effective active profiles/roles/localities, not a guarantee of partner availability. Frontend visual heat rendering and marketing attribution forwarding are excluded from this backend scope.

Affected PostgreSQL integration run: **120 passed in 69.69 seconds**, including marketing, analytics, leads, payments, notifications and public privacy/query regressions. Later follow-ups add monthly and concurrency assertions.

## M25 Hardening

Production startup validates strong secret, explicit HTTPS origins and account/public URLs, PostgreSQL/PostGIS connection and encrypted transport, authenticated TLS Redis, private S3 configuration, bounded signed URLs and TLS SMTP sender configuration. Celery verifies Redis certificates and accepts JSON task/result content only. Database URL credentials are decoded correctly. Proxy scheme trust is opt-in and requires ingress header stripping and restricted network access. Production does not load a repository `.env` file. SMTP/cache/database connection timeouts are bounded.

Refresh tokens have an explicit per-address/scoped rate limit. The latest anonymous browsing throttle removal, public intake limits, multipart pin parsing and complaint desk additions remain intact. Request observability uses generated correlation IDs, route templates, method, status and duration; it never logs request bodies/query strings. Sensitive/authenticated responses use no-store. JSON logging redacts common credentials/email strings and records exception type rather than potentially sensitive exception text. This does not claim exhaustive payload redaction at external ingress/error providers.

Focused PostgreSQL hardening/authentication/core/marketing regression: **127 passed in 29.72 seconds**. Existing public tests verify bounded query counts and object/field privacy. Local server fixture with **500 listings and 1,000 precomputed cells**: search **1.5316 s / 4 queries**, detail **0.0334 s / 3 queries**, panel **0.0502 s / 10 queries**. These are local single-run server timings, not representative mobile latency or a load/concurrency SLA. Python dependency advisory scan of the exact pinned production requirements reported **no known vulnerabilities**; this is not an OS-image or penetration-test certification.

## M26 Production preparation

Backend-only Docker build uses a pinned Python base digest, exact tested production Python dependencies, GDAL/GEOS, Gunicorn and UID 10001. No frontend context or secret build arguments are used. Compose separates web, worker, singleton Beat and release checks, drops capabilities, uses read-only roots/tmpfs, binds the API only on loopback, and never automatically migrates on startup. Existing identity-expiry, payout-due and lost/sold-review tasks are scheduled alongside notification/verification/marketing/analytics tasks; these existing task functions previously lacked Beat entries.

Offline production boot and Django security deployment checks passed in the non-root read-only image using synthetic configuration. Offline checks do not contact or validate live providers. Preflight separately runs general Django checks and treats Django security deployment warnings as failures; legacy OpenAPI deployment diagnostics remain a distinct schema-maintenance concern. New marketing/analytics methods include explicit request/response declarations. Operational counters report stale analytics, failed emails and bounded overdue-outbox counts without personal details.

[The production runbook](M26_PRODUCTION_RUNBOOK.md) covers configuration, image review, forward migrations, static serving, workers/Beat, HTTPS ingress, readiness/uptime/error/email/outbox monitoring, encryption evidence, daily full backups retained 30 days, private-file replication, quarterly restore and incident recovery. `docker/backup_database.sh` verifies a custom-format dump's archive and checksum; provider lifecycle and replication remain operator setup.

An isolated PostgreSQL 16/PostGIS dump-and-restore exercise passed using uniquely created synthetic source/destination databases. The restored consent history, market event, aggregate and audit counts matched; migration state/system checks passed; the restored immutability trigger still rejected deletion. No production database was backed up or restored. Private-object replica recovery and a full production-sized restore remain external acceptance work.

## New API contracts

| Method | Route under `/api/v1/` | Contract |
|---|---|---|
| GET | `marketing/` | Public currently active content/featured links; `language=sw|en` |
| GET, PUT | `marketing/consent/` | Own consent; PUT agreed, policy_version, version |
| GET | `marketing/click/` | Signed campaign token; validated redirect, no-store/no-referrer |
| GET, POST | `marketing/staff/content/`, `.../<uuid>/` | Staff listing/create/versioned replacement |
| GET, POST | `marketing/staff/featured/`, `.../<uuid>/` | Staff dates/enabled/listing/current version |
| GET, POST | `marketing/staff/campaigns/` | Count-only results or queue immutable bilingual campaign |
| GET | `analytics/` | Non-personal precomputed cells; bounded filters and freshness |
| GET | `analytics/export/` | Same filters and rows in `.xlsx`; separate export permission |

Campaign copy fields: subject_en/sw, body_en/sw, target_path, source_tag. Content fields: slug, kind BANNER/PAGE, title_en/sw, body_en/sw, target_path, source_tag, starts_at, ends_at, enabled, version. New item version is zero; updates use the returned version. Public search/detail accept `source_tag`; lead creation also accepts `source_tag` independently of its existing `source`. Invalid local paths/source tags/unknown overposted fields fail validation. Staff APIs do not provide deletion.

## Final validation and launch limits

The final complete PostgreSQL/PostGIS suite passed **1,650 tests in 277.28 seconds** against the final backend files, including monthly analytics, consent/delivery concurrency and scheduled-task registration. All 1,592 baseline cases remain green. Django system check reported zero issues; migration drift reported no changes; `git diff --check` passed. The final backend image built successfully and its non-root/read-only/GIS/offline-production checks passed. Synthetic recovery databases, dump and smoke environment were removed after verification.

Final scope: **57 files**, comprising 11 modified tracked files and 46 new untracked files, all under backend/documentation/operations paths. Both `git diff --name-only` and the complete nonignored untracked-file inventory (`git ls-files --others --exclude-standard`) were explicitly checked for `frontend/` paths and returned none. A direct tracked comparison against HEAD also confirmed frontend is unchanged. Nothing is staged. Branch remains main, HEAD remains `26fde45`. No commit, push or deployment occurred.

Validation encountered two corrected test-harness issues: a new concurrency assertion initially expected a list instead of the helper's tuple; a focused scheduler run attempted to reuse the database held by an active full suite and was rejected by PostgreSQL. Subsequent final tests ran sequentially and passed. Production preflight was refined to keep strict Django security checks separate from legacy OpenAPI deployment warnings. These intermediate failures are not reported as accepted results.

| Requirement | Backend outcome and acceptance boundary |
|---|---|
| MAR-01 | Dated eligible featured selection, authorized writes, versions and audit; frontend placement excluded |
| MAR-02 | Bounded plain-text bilingual banners/pages, periods and source links; frontend editing/rendering excluded |
| MAR-03 | Explicit opt-in/withdrawal, consent-filtered queue, recheck at delivery, retries/counts/signed clicks; live campaigns and preference UI unverified |
| MAR-04 | Source-tagged generated marketing targets and API attribution fields; received frontend forwarding is a separate integration |
| MON-01 | Precomputed stock/activity/monthly/coverage metrics and filters; historical/source/area gaps and observation weighting are explicit |
| MON-02 | Same filtered view exported as valid Excel OOXML with formula-safe text |
| MON-03 | Market panel/events/export omit buyer/owner personal details and exact coordinates |
| MON-04, NFR-01 | Precomputed bounded panel and measured local query/time budgets; production load/mobile network remains unverified |
| NFR-03 | Existing authorization/private-object regression plus refresh limits, strict production transport/configuration and proxy controls; edge/penetration testing remains operator work |
| NFR-04, NFR-05 | Consent/history guards, existing immutable domain boundaries and private storage configuration; infrastructure encryption/retention evidence remains external |
| NFR-06–08 | Readiness/observability/counters, validated backend image, backup/restore procedure and isolated restore evidence; live uptime/alerts/replication and quarterly operational sign-off remain external |
| NFR-02, NFR-09–12 | Existing backend media/language/settings behavior retained; frontend/network/browser/accessibility/provider aspects excluded |

No production acceptance is claimed for provider geography/maps, tax receipts, official WhatsApp operations, staff shifts/holiday policy, approved fees/banks, legacy partner onboarding, retention/wording/support identity policy, actual at-rest encryption, file replication, live SMTP, production-size recovery, mobile performance or uptime/alert operation. Passing code tests and deployment artifacts do not supply those external business/provider decisions.
