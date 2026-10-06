# M10–M13 investigation and implementation traceability

Investigation started 6 October 2026 at `ecb3a01` on `main`.
This document records findings and proposed implementation boundaries. It is
**not a completion report**. The proposed entities, services, routes and tests
below do not exist yet unless explicitly identified as existing.

## Working tree protection

The first commands were `git status`, `git diff --stat`, `git diff`, and
`git log --oneline -10`. The initial working tree was clean and synchronized
with `origin/main`. No interrupted, uncommitted changes were found, including
in `backend/apps/lister_identity/views.py`. No reset, restore, checkout, clean,
stash, commit or push was performed.

## Requirements authority

The repository has `docs/`, not `doc/`. Authoritative source:
`docs/backend_authorization/Oweru-Marketplace-SRD-v1.3.docx`.
Engineering guidance:
`docs/backend_authorization/Oweru_Marketplace_Backend_Development_Guide-v1.1.docx`.
The document README mentions historical SRD v1.2, but no separate v1.2 source
file was found in the current tracked documentation.

The root README and M01–M03 plan are stale about milestone progress and test
settings. `backend/pytest.ini` currently selects PostgreSQL tests; the alternate
test settings use SpatiaLite rather than plain SQLite. Neither old documentation
nor commit titles establish business-rule completeness.

## Existing architecture and prerequisites

* UUID custom User, required normalized email sign-in, unique phone, persisted
  public/operational categories, JWT rotation/blacklisting, email verification,
  purpose-bound hashed single-use confirmation tokens and deletion requests.
* Locality hierarchy and import/management services.
* ListerIdentity submission, Management review, configurable calendar-month
  expiry, expiry Celery task and sensitive-access logging. Evidence currently
  uses opaque references; it is not the financial document upload workflow.
* Permanent PostGIS PropertyRecord with locality consistency validation,
  protected relationships, spatial geometry and duplicate-review services.
* Permanent owner/agent Listing with whole-TSh Decimal prices, price constraints,
  documented lifecycle, private serializers, transactional services and photos.
* Media and MediaVariant with private keys, image processing, hashes and safe
  serializers. Existing media upload/access policies support only Listing and
  PropertyRecord; financial documents need purpose-specific ownership/access.
* PrivateMediaStorage abstraction supports unconfigured and in-memory backends
  only. Installing boto3 does not establish a production object-storage adapter.
* AuditLog/create_audit_log is the M04–M08 audit path. A separate historical
  AuditEvent stream remains installed and used by legacy authorization.
* PostgreSQL/PostGIS and Redis compose configuration; Celery app/autodiscovery.

No Lead, Deal, Payment, Payout, BankAccount, OwnerContact, RateTable, RateBand or
financial idempotency domain was found. Permission catalog entries and deferred
permission classes do not constitute implementations.

### Prerequisite defects requiring reconciliation

1. Two installed authorization stores are deliberately kept independent by
   tests. `apps.roles` contains Role/UserRole but no action-permission tables.
   `apps.roles.legacy_authorization` (app label `authorization`) contains
   Role/Permission/UserRole/RolePermission. User.has_role and
   User.has_marketplace_permission query `user_roles` in the latter store.
   M04–M08 services use user_has_role, querying canonical `roles` assignments.
   Registration and the Management authorization API write the permission-bearing
   store, while canonical assign/remove services write only canonical assignments.
2. Canonical user_has_role does not enforce persisted account-category
   compatibility. Canonical assignment checks Management role but not action
   permission or category; tests even permit public Management/Owner combinations.
   This contradicts the user's authorization safety requirements and SRD section 4.
3. Listing activation unconditionally includes
   `ActivationRequirement('lister_phone_confirmed', 'UNAVAILABLE')`, so normal
   activation cannot succeed. This must not be bypassed by simply deleting the gate.
4. Listing has no frozen rate-table relationship or agent-owner confirmation.
   Owner name/contact/bank fields are explicitly rejected by current listing
   services. A narrow OwnerContact/confirmation extension is necessary.
5. SensitiveConfirmation requires a User, defaults to 15 minutes and does not
   itself record owner delivery destination/decision. SRD 20.3 permits owners
   outside the account system and requires seven-day configurable owner links,
   outbox-only delivery, context, decision and recipient metadata. Reuse hashing
   and token patterns without pretending the existing flow meets those rules.
6. Financial PDF/image documents cannot be fed through the current image-only
   upload workflow or inherit Listing media visibility.

The user subsequently approved preserving both stores: M10–M13 action permission
checks use the permission-bearing store exclusively, with explicit new object
policies. Canonical information may be read only as domain context. Large
authorization consolidation is expressly outside this milestone; no third store,
OR grant fallback or destructive assignment migration is introduced.

## Requirement → implementation traceability

All rows below are missing domain implementation. Names are proposed, not final
API contracts. Action permissions must be combined with object participation and
fresh persisted active/category-compatible authorization.

| SRD / task requirement | Existing reusable foundation | Proposed model | Proposed service | Permission / object rule | Proposed API family | Audit | Required tests |
|---|---|---|---|---|---|---|---|
| LEAD-01 interest sources/contact snapshot | Listing/User | Lead | LeadCreationService | lead.create; eligible listing; buyer snapshot cannot impersonate account | leads collection | lead.created | enquiry/WhatsApp/viewing; privacy |
| LEAD-02 validated stages, notes, follow-up | AuditLog, transaction patterns | Lead, LeadTransition, LeadNote | LeadTransitionService | lead.update + own lister; WON internal only | lead transition/notes/follow-up | lead.transitioned/lost/follow_up_changed | legal/illegal stages; reason; direct WON rejection |
| LEAD-03 Closing prerequisites | Listing price/status constraints | Lead, OwnerContact/confirmation | DealClosingService | lead.update/deal.update + own lister | lead closing transition | final price; listing under offer | no price, inactive listing, unconfirmed owner, rollback |
| LEAD-04 Deal/payment freeze | Decimal pricing | Deal | DealClosingService + CommissionService | own lead; confirmed buyer; frozen listing rate | deals | deal.created/commission.calculated | duplicate + concurrent closing; all-or-nothing |
| LEAD-05 strict WON | PrivateMediaStorage/AuditLog | DealAgreement, Payment confirmations | DealCompletionService | no client WON; payment.confirm for Management review | agreement upload/confirm/review | agreement uploaded/confirmed/approved; deal.complete; lead.won; listing.sold | each missing condition; buyer completion denied; atomic completion |
| LEAD-06 private customers | own-listing queryset patterns | derive from Lead/LeadNote | LeadCustomerService | lead.view + own lister | leads customers | sensitive access where needed | cross-lister denial; private notes |
| LEAD-07 performance (Should) | lead timestamps once implemented | derived aggregates | LeadMetricsService | own lister/authorized Management | lead metrics | no financial mutation | conversions/response time; no M09 view tracking expansion |
| LEAD-08 lost/sold review | calendar-month helper/Celery | LostLeadReview | LostSoldReviewService/task | Management review scope | management review collection | lost_sold.flagged | same buyer/property; month boundary; repeat task |
| PAY-01/02 versioned rate maintenance | commission catalog permissions | RateTable, RateBand | RateTableService | commission.manage + Management; commission.view for listers | commissions rate tables/publish/current | rate_table.published | publish concurrency; immutable versions; revocation |
| SRD 9.1/9.3, PAY-03 financial calculation | Decimal pricing | Deal frozen fields; Listing rate FK | CommissionService | server calculated only | closing / explicit final-price update | calculated/recalculated | PAY-T1/T2/T3; inclusive integer boundaries; gaps; overlaps; residual |
| PAY-03 financial immutability | row locking patterns | Deal/payment activity | DealPricingService | own lister + deal.update; no payment activity | deal final-price mutation | final price/commission recalculated | proof/confirmation/complete prevent repricing |
| PAY-04/05 bank data | sensitive access audit helper | BankAccount, OwnerContact | BankAccountService | holder, authorized Management, active-deal buyer only | dedicated bank and instructions | sensitive_data.accessed; bank changed | agent denied owner bank; generic serializer omission |
| PAY-06 instructions/reference | frozen Deal values | Deal unique payment reference | PaymentInstructionsService | active-deal buyer; Management payment context | payment instructions | bank sensitive access | frozen amounts; unique reference; cross-buyer denial |
| PAY-07 payment evidence | private storage protocol | PaymentProof/Media ownership | PaymentProofService | payment.submit_proof + Deal buyer | payment proof upload/access | payment.proof_submitted/accessed | type/MIME/size; two transfers; duplicate content/key; private path omission |
| PAY-08 owner receipt | token hash/expiry/consume patterns | Payment owner confirmation | OwnerReceiptConfirmationService | authenticated owner or context-bound external-owner token; never agent | owner receipt/token decision | payment.owner_confirmed | impersonation; wrong purpose/subject; expired/reused token |
| PAY-09 Oweru receipt | Management catalog grant | Payment confirmation context | PaymentConfirmationService | payment.confirm + operational Management | Oweru confirm | payment.oweru_confirmed | amount/reference; revoked/inactive/unauthorized denial |
| SRD 9.5 independent status | no existing payment state | underlying confirmations + Deal state | PaymentStatusService | own financial context | safe Deal/payment read | business confirmation events | independent order; agreement gate; aggregate COMPLETE |
| PAY-11 tax receipt | private storage protocol | OfficialTaxReceipt | TaxReceiptService | payment.confirm + Management | official receipt record/access | official_receipt.recorded/accessed | EFD/VFD number/copy; duplicate; acknowledgement explicitly not tax receipt |
| PAY-10 due/paid payout | Celery/timezone | Payout, PayoutHistory | PayoutService/working-day helper | payout.record + Management; agent own status | payouts/read/paid | created/due/paid | frozen amount; weekends; task dedup; proof; tampering |
| PAY-12 complaint/manual hold | no Complaint model found | narrow deal hold policy record | PayoutHoldPolicy + PayoutService | payout.hold + Management; integration cannot bypass open hold | payout hold/release | held/released | open complaint blocks pay/release; repeated calls |
| Task financial idempotency | atomic/locking patterns only | IdempotencyRecord | FinancialIdempotencyService | authenticate + authorize before replay; actor/op/resource scope | required Idempotency-Key on mutations | mutation only on first success | all 15 mandatory cases incl PostgreSQL concurrent same key |
| Task atomic close/completion | AuditLog/transaction.atomic | Deal unique lead; payout unique deal | closing/completion services | object + action gates inside services | domain action endpoints | transactional existing AuditLog | audit failure rollback; simultaneous close/complete |

## Financial and transaction design constraints

* Rate bands use inclusive whole-TSh lower/upper limits matching the SRD example:
  0–50,000,000; 50,000,001–200,000,000; next lower = previous upper + 1;
  final upper may be unbounded. Validate complete coverage at publication.
* Published rate tables/bands remain immutable. A listing created before this
  domain exists has no historical published rate to reconstruct; do not silently
  pretend a newly published version existed at that listing's creation.
* Agent: owner transfer O(1−T); Oweru transfer S−owner transfer; agent payout
  O(T−X)+(S−O); Oweru retained = Oweru transfer−agent payout after whole-TSh
  rounding. Owner: owner transfer S(1−X); Oweru transfer S−owner transfer; zero
  agent payout. Exact transfer sum and retained+payout sum need constraints/tests.
* SRD requires whole shillings/residual to Oweru but does not specify half-tie
  rounding. Explicitly document and test the selected Decimal rounding policy.
* Lock rows in a consistent order; close must lock Listing and Lead, preventing
  different leads from simultaneously offering the same listing. A unique lead
  relation is necessary but does not alone prevent listing-level races.
* Completion must create the unique agent payout in the same transaction as
  COMPLETE/WON/SOLD. Owner deals must not create an agent payout.
* Idempotency claim/result and business/audit writes must share a transaction;
  database unique actor+operation+resource+key and locked stable resource serialize
  claims. Rollback removes unsuccessful claims. Fingerprint canonical values and
  file digests; retain no raw bank payload. Reject changed fingerprints with 409.
  Replay must repeat authorization checks and must not repeat audits or uploads.
* Storage writes are not database-transactional. Document orphan cleanup/recovery
  and avoid returning success before required private artifacts are persisted.

## Deferred integration boundaries

M09 is excluded. Full M14–M26 implementations and frontend edits are excluded.
Full-check offer and delivery hooks can exist without implementing verification
ordering/payment (PAY-13) or automatic VFD integration (PAY-14).
M20 must call a narrow payout-block policy when a deal complaint opens/closes;
manual payout release must not clear an independently open complaint block.
M21 must consume reliable pending owner-confirmation delivery intent and send
from Oweru's outbox; agent-facing APIs must never return bearer owner tokens.
No notification dispatch, full Complaint model, money custody or bank transfer
execution may be claimed from these boundaries.

## Environment investigation

Local `.venv/Scripts/python.exe` exists but refers to a missing Python 3.12
installation. This is an environment defect, not evidence of application failure.
Docker Desktop was initially stopped, then started in the background.
Existing `oweru-m09-test-db` and `oweru-m09-test-runner` are isolated on their own
network. Their names do not authorize M09 implementation. The runner mounts this
Marketplace workspace read-only. Older `backend-db-1`/`backend-api-1` containers
were left untouched. No database/volume/container was destroyed.
The interrupted runner had native GDAL/GEOS but no Django; repository requirements
were installed in that runner. No dependency files were changed.

Baseline Django check: no issues. Baseline `makemigrations --check --dry-run`:
no changes detected. Complete existing PostgreSQL/PostGIS test suite:
**1,070 executed, 1,070 passed, 0 failed, 0 skipped, 58.01 seconds**.
Command: `python -B -m pytest -p no:cacheprovider
--ds=config.settings.test_postgresql -q`, executed inside the isolated runner
from `/workspace/backend`. Successful database setup for that run exercised
the existing migration graph on a separate test database. No production
database migration was applied. These are baseline checks, not M10–M13
acceptance or financial-concurrency evidence. No new financial tests exist yet.

## Current work status

This document preserves the preimplementation investigation. Following the user's
authorization decision, implementation proceeded; see `M10_M13_BACKEND.md` for
actual models/services/APIs and operational boundaries. The proposed traceability
names above are investigation-era planning, not a substitute for the final code
and execution report. Frontend and historical migrations remain untouched.
