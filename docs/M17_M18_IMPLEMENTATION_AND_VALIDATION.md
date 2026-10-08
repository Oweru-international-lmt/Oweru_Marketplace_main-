# M17 / M18 implementation and validation

This report covers the backend implementation against SRD v1.3 and the Backend Development Guide. No commit or push was performed. M16 was extended, not rebuilt. The historical discovery report remains in `M14_M18_AUDIT_AND_DEPENDENCIES.md`.

## A. Required M14–M16 corrections

Submitted evidence is immutable; property creators and other known owners/relationships are excluded from verification; Full Check captures require measured boundaries; legacy field/document records cannot independently grant Level 3; exact-locality official eligibility and the prescribed questionnaire were added. Existing valid lower-level rules remain in place. Audit reproductions were converted into permanent regression tests.

## B. Evidence immutability

Append-only models/querysets reject mutation and deletion. PostgreSQL triggers protect immutable records, submitted captures/corners, referenced media and variants, including direct database updates. Authorized corrections create linked submission versions and preserve prior evidence. Frozen author, role, registration, device and timestamp information accompanies submissions. Private storage is reused; failed transactions clean newly written objects.

## C. Conflict policy

Server-side assignment and submission checks exclude property creators, listing listers, recorded owner accounts/contact phones, declared relationships and known matching professional/owner identity records. Eligibility is checked again when working and reading private tasks. Relationship declarations return unfinished professional work for reassignment and invalidate affected completed verification while retaining history.

## D. M15 capture

PostGIS corner points record accuracy, time and device. Full Check requires at least three measured corners and a valid submitted polygon; geography area and stated-area difference are calculated server-side. Configurable accuracy and discrepancy thresholds follow SRD defaults. Camera/gallery provenance, image/video metadata, missing-location, distance and age flags are retained. Boundary/public-layer overlaps are recorded. Capture access is bound to its verification task/job, preventing another buyer's same-property job from accessing or editing private evidence.

## E. Authoritative Level 3

The common server predicate requires a qualifying PASSED Full Check, matching final result, payment receipt, confirmed consent, report, current validity and no outstanding adverse result. Existing field/document records top out at Level 2. Public query annotations and persisted snapshots use that predicate. Expiry, property changes and listing-photo changes recalculate/invalidate without deleting history. Professionals and Local Officials cannot award Level 3.

## F. M16 extension

Approved coverage references the existing exact street/village Locality. Active role, action permission, coverage and conflict policy apply at assignment and submission. Eligible officials share the task; first submission closes it. Missing coverage alerts Management, later coverage permits assignment, and revocation reroutes pending work. The five questions are stored verbatim:

1. Is this plot in your Mtaa or village?
2. Do you know [owner name] as the owner of this plot?
3. Has this plot been sold or given to anyone else?
4. Is there any dispute over this plot?
5. Are the boundaries agreed with the neighbours?

Answers are YES/NO, comments are required for questions 2–5, and signed/stamped supporting evidence is required. The owner placeholder is populated from the recorded owner. Submitted results lock. The configurable default deadline is 14 days.

## G. M17 Professionals

The new professionals app uses existing User accounts and both pre-existing role stores. Exact types are Afisa Mipango Miji, Planner and Surveyor. Profiles contain registration, private identity information, region/district foreign-key coverage, active/inactive and verification metadata/timestamps. Management registration and updates are audited. Existing permissions and object policy govern APIs. Login delivery uses the existing secure reset/outbox boundary.

Shared verification tasks support assignment, acceptance, decline, reassignment, private evidence and locked versioned submission. Decline returns work to the responsible Verifier; the configurable default deadline is seven days. Type, coverage, current status, action permission and conflicts are rechecked. Permanent tests cover registration, coverage, transitions, immutability, audit, ownership conflicts and object isolation.

## H. M18 Full Check

Normalized jobs, tasks, assignments, submissions, proofs, receipts, consents, results, report versions, notices and histories reuse M14 infrastructure. Buyer orders support listed and outside properties. Signed configurable fee/scope quotes are frozen at ordering; no production fee is invented. M13 idempotency and private financial-document primitives support Phase 1 bank proof and Management confirmation with tax receipt. Financial documents are restricted to the paying buyer and authorized Management.

Payment precedes consent and work. Actual owners consent through their account; external owners use purpose-bound, sent, expiring, single-use confirmation links. Agents cannot impersonate owners. Domain-specific consent cannot be processed by the generic payment confirmation service. Missing owner contact and consent have separate deadlines.

The responsible Verifier starts prerequisite-controlled site, exact-locality official, selected professional and required registered-title registry tasks. Surveyor capture is supported. Mandatory evidence must be submitted before final review. The Verifier records risks, checks not completed and PASSED/PROBLEM_FOUND/NOT_COMPLETED. Adverse official answers prevent PASSED. Final results freeze the evidence manifest. Passed completion generates a private server PDF, durable buyer notice and effective Level 3. Failed/incomplete results cannot promote. Reliance is 30 days with the SRD six-calendar-month refresh ceiling; refresh creates another report version.

APIs are routed from the existing backend API: full-check ordering/quotes/payment/consent/orchestration/review/report; scoped verification task operations; professional profile management; official coverage; notices and verification settings. Arbitrary status PATCH transitions are not exposed.

## I. Transactions and concurrency

Critical services use atomic transactions, ordered property/job/task locks and database uniqueness. Shared financial idempotency handles payload collisions and replay authorization. Five PostgreSQL thread-based regressions cover duplicate orders, payment confirmation, exclusive acceptance, shared-official first submission and final review/report generation. Rollback tests cover state, audit and private-object cleanup.

## J. Forward migrations and invariants

Only new migrations were added: professionals 0001; local_officials 0002; site_capture 0002–0005; verification 0004–0009. They add normalized foreign keys, coverage/task indexes, conditional uniqueness, positive value/version constraints, consent authority checks, result/report enums and immutable/database workflow guards. Previously applied migrations were not rewritten.

## K. Existing audit system

Events cover professional profile/status/coverage changes; assignment, acceptance, decline, relationship declaration and evidence submission; official assignment/questionnaire; order, proof/payment, consent, capture and task creation; Verifier review/result; report generation; notices; Level 3 changes; expiry and invalidation. Financial and report access remains private and sensitive reads are audited. No second audit framework was introduced.

## L. PostgreSQL/PostGIS validation

Pre-change baseline: 1,405 collected/passed, 0 failed, 0 skipped (118.61 seconds). Django system check passed and migration drift was clean. Final counts and commands are appended below after completion.

## M. End-to-end acceptance

Permanent acceptance coverage exercises paid buyer order → actual owner consent → measured site boundary → exact-locality official five-question submission → Planner acceptance/evidence → required registry submission → Verifier review → authoritative result/private PDF → Level 3. Additional valid scenarios cover Surveyor capture with Afisa Mipango Miji and outside untitled properties. Mandatory-prerequisite omission, adverse result, expiry, invalidation and private access failures are tested.

## N–O. Created and modified files

Exact repository file inventories are appended below. Existing test assertions were updated for the corrected Level 3 rules; no baseline test functions were intentionally removed. Diagnostic audit/PDF previews are excluded and cleaned.

## P. Deferred integrations / deployment configuration

Automated WhatsApp/email provider delivery remains at the existing M21 outbox boundary; manual authorized send/mark-sent workflows are available. Satellite imagery/provider integration and authoritative public-map datasets require external setup; OSM fallback and unavailable-source flags are implemented. Registry checks use the SRD manual staff workflow. Production fee/scope, confirmation/reset URLs and private storage must be configured. No frontend work was requested or changed.

## Q. SRD policy gaps and scope limits

SRD does not specify how to clear an adverse Full Check flag. The backend conservatively prevents later Level 3 while an uninvalidated PROBLEM_FOUND remains; no unreviewed automatic clearing mechanism was invented. Working-day deadlines use weekdays, without an external holiday calendar. Broader legacy lower-level LOCATION semantics and M16 onboarding discrepancies remain documented in the historical audit and were not broadly redesigned. This report establishes tested Phase 1 backend behavior, not completion of external integrations or all historical milestone gaps.

## R–S. Git safety

Exact tracked diff statistics and short status are appended below. Untracked new implementation files are listed separately because ordinary `git diff --stat` excludes them. No commit, push, frontend modification, credentials, database dump, private evidence or generated private report is included.

### Created files
```text
backend/apps/local_officials/full_check.py
backend/apps/local_officials/full_check_api.py
backend/apps/local_officials/migrations/0002_officiallocalitycoverage.py
backend/apps/local_officials/tests/test_full_check_coverage.py
backend/apps/professionals/__init__.py
backend/apps/professionals/api.py
backend/apps/professionals/apps.py
backend/apps/professionals/migrations/0001_initial.py
backend/apps/professionals/migrations/__init__.py
backend/apps/professionals/models.py
backend/apps/professionals/services.py
backend/apps/professionals/tests/__init__.py
backend/apps/professionals/tests/test_professionals.py
backend/apps/professionals/urls.py
backend/apps/site_capture/evidence.py
backend/apps/site_capture/full_check_api.py
backend/apps/site_capture/migrations/0002_sitecapture_area_difference_percent_and_more.py
backend/apps/site_capture/migrations/0003_sitecapture_overlap_findings_captureasset_and_more.py
backend/apps/site_capture/migrations/0004_capture_media_guards.py
backend/apps/site_capture/migrations/0005_sitecapture_verification_task.py
backend/apps/site_capture/tests/test_capture_provenance.py
backend/apps/site_capture/tests/test_full_check_measurements.py
backend/apps/verification/access.py
backend/apps/verification/configuration.py
backend/apps/verification/conflicts.py
backend/apps/verification/deadlines.py
backend/apps/verification/full_check_api.py
backend/apps/verification/full_check_services.py
backend/apps/verification/full_check_urls.py
backend/apps/verification/immutability.py
backend/apps/verification/job_models.py
backend/apps/verification/levels.py
backend/apps/verification/migrations/0004_propertyverificationevidence_author_role_and_more.py
backend/apps/verification/migrations/0005_submitted_evidence_guards.py
backend/apps/verification/migrations/0006_tasksubmission_signed_and_stamped_and_more.py
backend/apps/verification/migrations/0007_full_check_database_guards.py
backend/apps/verification/migrations/0008_verificationlevelsnapshot.py
backend/apps/verification/migrations/0009_fullcheckreceipt_full_check_receipt_positive_and_more.py
backend/apps/verification/outbox.py
backend/apps/verification/relationships.py
backend/apps/verification/reports.py
backend/apps/verification/signals.py
backend/apps/verification/task_api.py
backend/apps/verification/task_services.py
backend/apps/verification/task_urls.py
backend/apps/verification/tests/test_full_check.py
backend/apps/verification/tests/test_full_check_concurrency.py
backend/apps/verification/tests/test_full_check_invariants.py
backend/apps/verification/tests/test_full_check_partner_variants.py
backend/apps/verification/tests/test_prerequisite_regressions.py
docs/M14_M18_AUDIT_AND_DEPENDENCIES.md
docs/M17_M18_IMPLEMENTATION_AND_VALIDATION.md
```

### Modified files
```text
backend/apps/lister_identity/services.py
backend/apps/listings/services.py
backend/apps/listings/tests/test_public_verification_engine.py
backend/apps/local_officials/management_urls.py
backend/apps/local_officials/models.py
backend/apps/local_officials/policies.py
backend/apps/local_officials/tests/test_cross_domain_integration.py
backend/apps/local_officials/tests/test_field_workflow_integration.py
backend/apps/local_officials/urls.py
backend/apps/media/services.py
backend/apps/payments/confirmations.py
backend/apps/payments/views.py
backend/apps/site_capture/models.py
backend/apps/site_capture/serializers.py
backend/apps/site_capture/services.py
backend/apps/site_capture/tests/test_api.py
backend/apps/site_capture/tests/test_media_integration.py
backend/apps/site_capture/tests/test_models_services.py
backend/apps/site_capture/tests/test_promotion.py
backend/apps/site_capture/tests/test_verification_integration.py
backend/apps/site_capture/urls.py
backend/apps/site_capture/views.py
backend/apps/verification/apps.py
backend/apps/verification/models.py
backend/apps/verification/services.py
backend/apps/verification/tasks.py
backend/apps/verification/tests/test_field_lifecycle.py
backend/apps/verification/tests/test_models_services.py
backend/apps/verification/tests/test_property_invalidation.py
backend/config/api_urls.py
backend/config/settings/base.py
backend/requirements.txt
```

### git diff --stat (tracked files)
```text
 backend/apps/lister_identity/services.py           |  18 ++-
 backend/apps/listings/services.py                  |   4 +
 .../tests/test_public_verification_engine.py       |   7 +-
 backend/apps/local_officials/management_urls.py    |   3 +
 backend/apps/local_officials/models.py             |  18 ++-
 backend/apps/local_officials/policies.py           |   3 +
 .../tests/test_cross_domain_integration.py         |   4 +-
 .../tests/test_field_workflow_integration.py       |   6 +-
 backend/apps/local_officials/urls.py               |   2 +
 backend/apps/media/services.py                     |  49 +++---
 backend/apps/payments/confirmations.py             |   4 +
 backend/apps/payments/views.py                     |   6 +-
 backend/apps/site_capture/models.py                |  55 +++++++
 backend/apps/site_capture/serializers.py           |  17 +++
 backend/apps/site_capture/services.py              | 164 ++++++++++++++++++++-
 backend/apps/site_capture/tests/test_api.py        |   2 +-
 .../site_capture/tests/test_media_integration.py   |   3 +-
 .../site_capture/tests/test_models_services.py     |   4 +-
 backend/apps/site_capture/tests/test_promotion.py  |   7 +-
 .../tests/test_verification_integration.py         |  16 +-
 backend/apps/site_capture/urls.py                  |   4 +
 backend/apps/site_capture/views.py                 |  20 ++-
 backend/apps/verification/apps.py                  |   6 +
 backend/apps/verification/models.py                |  13 +-
 backend/apps/verification/services.py              |  28 +++-
 backend/apps/verification/tasks.py                 |  12 ++
 .../verification/tests/test_field_lifecycle.py     |   4 +-
 .../verification/tests/test_models_services.py     |   4 +-
 .../tests/test_property_invalidation.py            |   2 +-
 backend/config/api_urls.py                         |  13 ++
 backend/config/settings/base.py                    |   8 +
 backend/requirements.txt                           |   1 +
 32 files changed, 442 insertions(+), 65 deletions(-)
```

### git status --short
```text
 M backend/apps/lister_identity/services.py
 M backend/apps/listings/services.py
 M backend/apps/listings/tests/test_public_verification_engine.py
 M backend/apps/local_officials/management_urls.py
 M backend/apps/local_officials/models.py
 M backend/apps/local_officials/policies.py
 M backend/apps/local_officials/tests/test_cross_domain_integration.py
 M backend/apps/local_officials/tests/test_field_workflow_integration.py
 M backend/apps/local_officials/urls.py
 M backend/apps/media/services.py
 M backend/apps/payments/confirmations.py
 M backend/apps/payments/views.py
 M backend/apps/site_capture/models.py
 M backend/apps/site_capture/serializers.py
 M backend/apps/site_capture/services.py
 M backend/apps/site_capture/tests/test_api.py
 M backend/apps/site_capture/tests/test_media_integration.py
 M backend/apps/site_capture/tests/test_models_services.py
 M backend/apps/site_capture/tests/test_promotion.py
 M backend/apps/site_capture/tests/test_verification_integration.py
 M backend/apps/site_capture/urls.py
 M backend/apps/site_capture/views.py
 M backend/apps/verification/apps.py
 M backend/apps/verification/models.py
 M backend/apps/verification/services.py
 M backend/apps/verification/tasks.py
 M backend/apps/verification/tests/test_field_lifecycle.py
 M backend/apps/verification/tests/test_models_services.py
 M backend/apps/verification/tests/test_property_invalidation.py
 M backend/config/api_urls.py
 M backend/config/settings/base.py
 M backend/requirements.txt
?? backend/apps/local_officials/full_check.py
?? backend/apps/local_officials/full_check_api.py
?? backend/apps/local_officials/migrations/0002_officiallocalitycoverage.py
?? backend/apps/local_officials/tests/test_full_check_coverage.py
?? backend/apps/professionals/
?? backend/apps/site_capture/evidence.py
?? backend/apps/site_capture/full_check_api.py
?? backend/apps/site_capture/migrations/0002_sitecapture_area_difference_percent_and_more.py
?? backend/apps/site_capture/migrations/0003_sitecapture_overlap_findings_captureasset_and_more.py
?? backend/apps/site_capture/migrations/0004_capture_media_guards.py
?? backend/apps/site_capture/migrations/0005_sitecapture_verification_task.py
?? backend/apps/site_capture/tests/test_capture_provenance.py
?? backend/apps/site_capture/tests/test_full_check_measurements.py
?? backend/apps/verification/access.py
?? backend/apps/verification/configuration.py
?? backend/apps/verification/conflicts.py
?? backend/apps/verification/deadlines.py
?? backend/apps/verification/full_check_api.py
?? backend/apps/verification/full_check_services.py
?? backend/apps/verification/full_check_urls.py
?? backend/apps/verification/immutability.py
?? backend/apps/verification/job_models.py
?? backend/apps/verification/levels.py
?? backend/apps/verification/migrations/0004_propertyverificationevidence_author_role_and_more.py
?? backend/apps/verification/migrations/0005_submitted_evidence_guards.py
?? backend/apps/verification/migrations/0006_tasksubmission_signed_and_stamped_and_more.py
?? backend/apps/verification/migrations/0007_full_check_database_guards.py
?? backend/apps/verification/migrations/0008_verificationlevelsnapshot.py
?? backend/apps/verification/migrations/0009_fullcheckreceipt_full_check_receipt_positive_and_more.py
?? backend/apps/verification/outbox.py
?? backend/apps/verification/relationships.py
?? backend/apps/verification/reports.py
?? backend/apps/verification/signals.py
?? backend/apps/verification/task_api.py
?? backend/apps/verification/task_services.py
?? backend/apps/verification/task_urls.py
?? backend/apps/verification/tests/test_full_check.py
?? backend/apps/verification/tests/test_full_check_concurrency.py
?? backend/apps/verification/tests/test_full_check_invariants.py
?? backend/apps/verification/tests/test_full_check_partner_variants.py
?? backend/apps/verification/tests/test_prerequisite_regressions.py
?? docs/M14_M18_AUDIT_AND_DEPENDENCIES.md
?? docs/M17_M18_IMPLEMENTATION_AND_VALIDATION.md
```

### Final focused results

PostgreSQL/PostGIS focused run: **289 collected, 289 passed, 0 failed, 0 skipped**, 101.84 seconds.

| Group | Collected | Passed | Failed | Skipped |
|---|---:|---:|---:|---:|
| M14 including prerequisite regressions | 62 | 62 | 0 | 0 |
| M15 Site Capture | 106 | 106 | 0 | 0 |
| M16 Local Officials | 46 | 46 | 0 | 0 |
| M17 Professionals | 29 | 29 | 0 | 0 |
| M18 Full Check including concurrency/variants | 46 | 46 | 0 | 0 |

The end-to-end acceptance scenarios passed in this run. Django system check: **0 issues**. `makemigrations --check --dry-run`: **No changes detected**. `git diff --check`: **passed**. No removed test definitions or new skip markers were found in tracked test diffs. Baseline growth is 94 tests.

Command: `docker exec oweru-m09-test-runner python -B -m pytest -p no:cacheprovider --ds=config.settings.test_postgresql` (focused run adds the M14�M18 test paths).

### Authorization and scheduling details

Existing action permissions are reused: `partner.manage`, `verification.order`, `verification.assign_task`, `verification.complete_task`, `verification.record_result`, `payment.submit_proof`, `payment.confirm`, `settings.manage`, `outbox.send` and the existing listing action where owner/agent capture requires it. Every private object operation also applies job/task ownership, role/status, coverage and conflict policy. No new authentication or permission system was created.

The existing Celery architecture runs idempotent deadline/expiry processing every 15 minutes and nightly level recalculation. Repeated runs preserve terminal history and do not duplicate deadline/expiry transitions or their audit events. Submitted result/report history remains available through authorized private access after public verification expires.

Database report validation included rendered English and Swahili output: two pages each, with no clipped text, exposed private identity numbers, financial storage keys or staff personal names. Temporary rendered previews were removed after inspection.

### Final complete regression result

Exact final code, PostgreSQL/PostGIS: **1,499 collected, 1,499 passed, 0 failed, 0 skipped**, **183.36 seconds**. Exit code 0. This is **94 more passing tests** than the verified pre-change baseline of 1,405. The final run includes the generic-confirmation purpose guard and its permanent regression. No temporary audit probes or PDF QA tests were included in this count.

Final safety: only backend code and the two reports are changed; no frontend changes, historical migration rewrites, environment files, credentials, private evidence, generated PDF reports, database dumps or temporary extraction files are shipped. Task-created diagnostic files and container preview/migration artifacts were cleaned. The existing archive tree was preserved. No commit or push was performed.
