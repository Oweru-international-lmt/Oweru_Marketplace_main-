# M14 through M18 audit and implementation dependencies

The pulled M14, M15 and M16 code passes its existing PostgreSQL/PostGIS regression suite, but does not implement the milestone contracts in SRD v1.3. M17 and M18 must not be described as ready to build on a requirements-clean verification foundation. In particular, the current Level 3 calculation has no full-check prerequisite, and the local-official implementation cannot provide M18's required local-office task. M16 remains unchanged as instructed.

## Scope and sources

Audit date: 7 October 2026. Repository HEAD: `0f9f8583c569bb7ea05b7a5d8001385c418c0827`.

Reviewed the pulled commit changes, models, migrations, services, serializers, URLs, views, task entry points, integration tests, private media contracts, property authorization, canonical roles, and relevant prior financial boundaries.

Business authority: [Oweru Marketplace SRD v1.3](backend_authorization/Oweru-Marketplace-SRD-v1.3.docx), especially sections 2–4, 10–15, 20, 22–23 and 25–26. Implementation guide: [Backend Development Guide v1.1](backend_authorization/Oweru_Marketplace_Backend_Development_Guide-v1.1.docx), especially phases 12, 17–22, 29, service architecture, background jobs, testing strategy and roadmap M14–M18. The SRD takes precedence over the guide and over tests encoding incompatible behavior.

| Milestone | Pulled commit | Actual implementation |
|---|---|---|
| M14 | `97bfa20` | Document/field submissions, review transitions, evidence references, expiry services, computed ladder and public query integration |
| M15 | `30f52ff` | Observed point/optional polygon, draft/submitted lifecycle, private image integration and promotion to PropertyRecord |
| M16 | `0f9f858` | Official profiles, region/district/ward jurisdiction assignments and scoped approval/rejection of M14 FIELD records |

No application code or historical migrations were changed during this audit. The probes use separate disposable test data and deliberately assert observed defects; they are not SRD acceptance tests.

## Executed regression baseline

Docker Desktop was initially stopped. Started the existing isolated `oweru-m09-test-db` and `oweru-m09-test-runner`; no production database migration, container deletion or volume deletion was performed. The runner working directory is `/workspace/backend`. Its historical M09 name does not change this task's scope.

Executed in the runner:

```text
python -B -m pytest -p no:cacheprovider --ds=config.settings.test_postgresql -q
1405 passed in 118.61s

python -B manage.py check --settings=config.settings.test_postgresql
System check identified no issues (0 silenced).

python -B manage.py makemigrations --check --dry-run --settings=config.settings.test_postgresql
No changes detected
```

The interruption discarded access to the first test process. Its output is not counted as evidence. The recorded full suite is the subsequent completed run. PostgreSQL/PostGIS test database setup exercises the migration graph; SQLite was not substituted. No tests were reported skipped or failed.

Separate audit probes:

```text
python -B -m pytest -p no:cacheprovider --ds=config.settings.test_postgresql -q \
  /workspace/.archive_review/test_m14_m16_audit_probes.py
4 passed in 9.13s
```

The existing suite is clean as a regression baseline. The specification baseline is not clean: existing tests explicitly expect document plus field approval to grant Level 3. Adding full-check tests without correcting this contract would preserve a false prerequisite.

## Findings in priority order

### Critical M14 ladder disagrees with SRD

`backend/apps/verification/services.py`, `get_effective_verification_level` and `annotate_listing_queryset_with_effective_verification_level`, compute a sequential identity → DOCUMENT → FIELD ladder. A FIELD approval produces Level 3. There is no VerificationJob, paid order, owner consent, registry result, verifier risk assessment or full-check result behind that Level 3.

SRD section 10 requires Level 2 from a valid location check and Level 3 from a valid passed full check. It specifies the highest valid condition, rather than requiring every lower condition to remain valid. Thus a later identity expiry currently collapses a still-valid higher property verification as well. Tests in `verification/tests/test_models_services.py`, `listings/tests/test_public_verification_engine.py`, and site-capture verification integration encode the current incompatible ladder.

The public labels in `lister_identity/services.py` are `Not verified`, `Identity verified`, `Property verified`, and `Field verified`. They do not provide the approved SRD wording, ownership disclaimer, full-check completion/expiry dates, or partner/check panel. The label currently says `Field verified`, not `Oweru Verified`; the defect is the underlying Level 3 condition, not an allegation that the reserved badge text already appears.

Required before M18 activation: canonical LOCATION/FULL/OUTSIDE_FULL results; an effective-result evaluator shared by queries and serializers; SRD labels and dates; adverse-result gating; material-change invalidation; expiry/refresh semantics. Do not reinterpret historical FIELD rows as passed ownership checks.

### High M14 evidence is mutable after submission

`PropertyVerificationEvidence.save` normalizes a reference but does not check submission status or enforce a version. Neither its manager nor `delete` forbids mutation/deletion. The audit probe successfully overwrote and deleted evidence attached to a submitted document record.

This conflicts with VER-04 and NFR-05. The probe demonstrates ORM behavior, not an exposed public update/delete endpoint. Generic foreign-key PROTECT protects a referenced parent; it does not make the referencing evidence row immutable. A proper submission boundary must freeze evidence and preserve corrections as new versions, including author, role and device provenance required by VER-03.

### High M16 is a jurisdiction policy rather than the required local-office workflow

`LocalOfficialProfile` stores a user, official number and active flag. `OfficialJurisdictionAssignment` permits REGION/DISTRICT/WARD coverage. There is no exact Locality assignment, invited/awaiting-approval registration lifecycle, official position, ID/photo/stamp, confirming staff member, five-question evidence, stamped submission, shared local-office task, Needs official state, first-complete-submission behavior, or 14-day task timeout.

LOC-01 through LOC-07 and FUL-04 therefore cannot be satisfied by the current M16 API. A ward or regional FIELD-review queue is not exact street/village routing. Deactivating a profile blocks the scoped review policy, but does not set `User.is_active=False`; do not claim that profile deactivation prevents ordinary login as LOC-06 requires.

M16 must remain untouched under the user's instruction. M18 must not fake completion by accepting a ward-level FIELD approval or implementing the missing M16 workflow under a different app name.

### High conflict-of-interest enforcement is incomplete

M14 approval rejects a reviewer who is also the submitter. The M16 review policy checks current jurisdiction but not ownership, listing or declared relationship. The probe made a property's creator the assigned official and the review policy still returned true, while the submitter remained a different user.

VER-06 requires blocking assignment for owners, listers and declared relationships, not merely blocking self-review at approval time. There is no declared-relationship registry in the pulled verification domain. M17 assignment must enforce conflicts independently; M18 official routing needs the corresponding M16 contract.

### High M15 lacks required capture measurements and provenance

The SiteCapture schema has one observed point and an optional polygon. There are no per-corner accuracy/time/device records, minimum corner count at submission, derived measured area, accuracy threshold, area-difference flag, photo distance/age/missing-location flags, video workflow, loaded-layer overlap findings, or provider availability contract. A probe submitted a capture with one point and no boundary successfully.

Validating GeoJSON point/polygon syntax and SRID 4326 is useful, but does not satisfy MAP-01 through MAP-06. The tests accept world coordinate extremes; they prove syntax bounds, not the Tanzania location check in VER-02. MAP-07 and MAP-08 are Should requirements and should not be confused with missing Must requirements. The generic capture mutation services reject submitted edits and private media mutation is draft-only, which are useful existing boundaries.

M17's surveyor work cannot claim PRO-04 compliance by accepting an opaque capture ID from this implementation. Surveyors also lack task-specific access: capture creation uses PropertyRecord creator/Management permissions, with no assigned-surveyor capability. Granting surveyors general property edit permission would exceed the intended scope.

### High M14 review APIs omit the evidence needed for review

Document review serializers expose identifier, property identifier, kind, status and dates, but not checklist answers, evidence or authorized evidence access. The local-official serializer exposes administrative areas and metadata, but not the five questions, owner name, stamped report or submission evidence. Privacy filtering is valuable; the workflow still needs a separate authorized private evidence channel with sensitive-access audit records.

### Medium expiry and event integration differ from the requirements

Both document and field expiry default to 12 months in `config/settings/base.py`, whereas VER-05 specifies six-month location checks and 30-day full-check reliance with refresh up to six months. Settings are environment values rather than management-editable database configuration.

The expiry task is defined, but no Celery beat schedule for nightly recalculation is configured in the reviewed settings or `config/celery.py`. The ladder is derived on reads and queries; no stored per-listing level/event recalculation implementation satisfies the literal LVL-01 storage contract. Approved rows whose timestamp has elapsed continue to occupy the partial unique active slot until the expiry service runs.

Property-field updates invoke invalidation for a useful set of material facts. Listing photo add/remove paths do not invoke verification invalidation, although VER-05 includes photo changes. Capture promotion does invoke canonical property updates and thereby invalidation; merely collecting independent draft observations should not itself imply a verified property change.

### Medium verification status depends on the reader's identity

`PropertyVerificationStatusView` passes `request.user` to the evaluator for a property accessible to Management. This produces the reader's identity prerequisite rather than the listing's lister or the property's valid check result. A probe demonstrated Level 2 for the lister and Level 0 for another authorized role against the same property. Public listing queries use `lister_id`, so this is an inconsistent private status context, not proof that every public read depends on the requester.

### Medium operational documentation is stale

README correctly introduces PostgreSQL/PostGIS at the top, then says the default suite remains SQLite. `backend/pytest.ini` defaults to `config.settings.test_postgresql`; `test.py` actually selects Spatialite, and `test_postgresql.py` replaces that database. Resolve these contradictory setup statements before delivery documentation is considered reliable.

## Existing strengths to preserve

- PropertyRecord remains the canonical permanent reference; new job/order/task entities should reference it rather than duplicate its identity.
- Role and actor checks use persisted active assignments, rather than caller-supplied role strings. M16 coverage checks reevaluate profile and assignment activity.
- Mutation services use transactions, row locks and transactional safe audit metadata; approved/rejected/revoked model pairs and active uniqueness have database constraints.
- Capture mutations use strict serializers and reject submitted updates. Geometry validation rejects malformed input and mismatched SRIDs. Promotion invokes canonical property validation and verification invalidation.
- Capture images use the private media abstraction and bounded API pagination. Public listing serialization avoids exact geometry and internal evidence references.
- The existing finance workflow is a separate deal domain. It should not be overloaded with a fake Deal to collect full-check fees.

These strengths establish reusable patterns, not completion of the missing requirements above.

## M17 Professionals requirements and dependencies

| Requirement | Required implementation | Dependencies and acceptance evidence |
|---|---|---|
| PRO-01 | Management-created partner account/profile with name, one of Afisa Mipango Miji/Planner/Surveyor, registration number, national ID, phone, email, regions/districts and status | Existing User/canonical roles/audit; private treatment of national ID; unique account handling; transactional provisioning; manual Oweru outbox delivery of login/setup instructions. Never return reusable credentials in generic serializers or audit payloads. |
| PRO-02 | Verifier chooses only active professionals of the required type who cover the current property district | Persisted role/profile checks; canonical District coverage; property-linked task; VER-06 relationship declarations; tests for inactive/revoked role, wrong type/district and ownership/listing/declared conflicts. |
| PRO-03 | Assignee dashboard, alert and accept/decline actions; decline returns task to verifier | Explicit assignment history; scoped reads; transactional notification intent; tests for cross-professional access, duplicate decisions, reassignment and stale assignee actions. |
| PRO-04 | Seven-day configurable deadline; findings, private report and evidence; surveyor uses valid site capture | Database settings and deadline worker; private validated upload/signing; M15 corner/provenance/measurement capabilities; task-specific surveyor capture access. Timeout must be observable to the owning verification job. |
| PRO-05 | Permanently attributed submission with frozen professional name/registration and evidence | Versioned immutable submission records; author/role/device/time; no overwrite/delete; corrections append versions; tests for profile edits after submission, audit rollback and direct ORM protections. |

Professional tasks require an explicit verification job/task contract that current M14 does not provide. A standalone professional task collection may be a useful foundation, but must not be reported as the complete SRD assignment/report workflow without job integration and surveyor support. Full notification dispatch remains M21; a durable delivery intent alone must be described accurately.

## M18 Full Check requirements and dependencies

| Requirement | Required implementation | Dependencies and acceptance evidence |
|---|---|---|
| FUL-01 / PAY-13 | Buyer orders listed/outside property; fee and scope presented before ordering; frozen amount, reference, private proof and authorized receipt confirmation | PropertyRecord/outside input validation, Buyer role, database-configurable fee without inventing Director-approved production pricing; verification payment distinct from Deal payment; replay/concurrency tests. |
| FUL-02 | Payment → owner consent; account decision for owner listing; purpose-bound single-use external-owner link for agent listing; missing-contact deadline of three working days; seven-day response deadline | Existing confirmation hashing/locking patterns need subject/recipient/content/device decision context; manual outbox delivery, never an agent-visible bearer token; calendar/timezone policy; refusal/no reply produces Not completed. |
| FUL-03 | Owner/agent site task or verifier-selected surveyor | M15 complete capture contract and M17 assignee-specific authority; submitted evidence version tied to job/property snapshot. |
| FUL-04 | Automatic exact street/village routing, conflict exclusion, Needs official, five questions and signed/stamped evidence | Missing M16 capability. No broader jurisdiction fallback can satisfy this requirement. This is a hard dependency under the instruction not to implement M16. |
| FUL-05 | Verifier assigns needed professional tasks | M17 type/district/active/conflict filters, decisions, evidence and deadlines; declined tasks return for reassignment rather than silently satisfying the job. |
| FUL-06 | Registered-title Land Registry search recorded by the responsible verifier | Explicit title applicability and task evidence; missing required registry evidence blocks review/result. No registry integration is fabricated. |
| FUL-07 / VER-07 | Responsible verifier risk assessment and Passed/Problem found/Not completed; versioned PDF report; private paying-buyer access and appropriate notification | Complete immutable evidence basis; private PDF rendering/storage; durable notification intent/M21 delivery; adverse flag internal only; no public fraud label; other buyers/listers cannot read adverse report. |
| VER-01/03/04/05 | Job, tasks, checklist, status history, evidence/provenance, submission locks and expiry | Repair/extend M14 semantics, preserve historical rows without automatic promotion; atomic result/report intent and no partial successful check. |
| LVL-01/02 | Passed valid full check alone authorizes Level 3; event/nightly recalculation and approved fixed translated wording | Shared query/evaluator contract, invalidation on property/photo changes, 30-day reliance/refresh ceiling, public date panel and untitled-land warning. |

Required full-check state machine: AWAITING_PAYMENT → AWAITING_CONSENT → IN_PROGRESS → UNDER_REVIEW → PASSED or PROBLEM_FOUND. Consent refusal/no response and required task timeout produce NOT_COMPLETED. No task may start before paid consent, no review may proceed with missing mandatory submissions, and no Level 3 may be granted by partner approval alone. Responsible Verifier ownership and persisted authority must be rechecked on every mutation and replay.

M18 also depends on a report-generation adapter, private document access, M21 notification delivery contracts, management-editable configuration, and working-day policy. These may have narrow foundations implemented within M17/M18 if authorized, but missing dependent milestones must remain explicit. Do not implement M19, M20, or all of M21/M22 incidentally.

## Baseline decision and next work

Regression baseline: passed. Specification/dependency baseline: not clean. No M16 implementation or fixes were made. No M17/M18 application implementation has begun.

Before claiming M18 completion, resolve the M14 semantics/evidence and M15 capture requirements, and provide an SRD-compliant M16 interface from the milestone's owner. If implementation proceeds while M16 remains excluded, M18 must keep the local-office dependency blocked and cannot be delivered as an end-to-end full check. A choice between that explicitly partial scope and stopping at the audit was requested from the user; no response is presumed by this report.
