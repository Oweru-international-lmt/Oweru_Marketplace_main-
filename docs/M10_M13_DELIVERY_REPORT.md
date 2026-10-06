# M10–M13 implementation delivery report

Project: current Oweru Marketplace backend, based on `ecb3a01`.
No Oweru PA System architecture/database was used. No M09 or frontend feature was
implemented. No commit or push was performed.

## Initial audit and preserved work

The initial working tree was clean. There were no inherited authorization or
lister_identity/views.py edits to discard or reconcile. Existing M01–M08 services,
models, 1,070 tests and historical migrations were preserved. The audit document
`M10_M13_INVESTIGATION.md` records the initial architecture and prerequisite defects.
SRD v1.3 is authoritative over the guide and older repository descriptions.

The user approved legacy authorization as the exclusive new action-permission
source while keeping canonical M04–M08 behavior. No third authorization system,
OR fallback, wildcard Management grant or bulk role migration was introduced.

## Implemented domains

**M10:** Lead/contact snapshots, three interest sources, validated sequential
pipeline, reasoned Lost, history, private notes/follow-up, own customer list,
scoped pipeline metrics and configurable calendar-month Lost/sold review flags.
Closing invokes the transactional Deal service; WON is internal completion only.
External customers can be recorded without inventing a Buyer account.

**M11:** unique Deal/Lead and OPEN-Deal/Listing constraints, concurrency-safe
Closing, historical financial/participant/bank snapshots, private agreement upload,
explicit lister exact-price assertion and Management approval, strict atomic
COMPLETE/WON/SOLD/payout completion. Unpaid Closing cancellation retains a CANCELLED
snapshot and releases the listing; financial-activity reversals are blocked.

**M12:** draft/published RateTable versions and bands, gap/overlap/rate validation,
published-version immutability, listing-creation rate freezing, creation/publication
transaction serialization, final-price band selection, dedicated Decimal formulas,
stored whole-TSh reconciliation, pre-activity repricing and database freezing guards.

**M13:** sensitive BankAccount/OwnerContact, frozen two-transfer instructions,
unique Oweru reference, private validated proofs, authenticated owner or secure
external-owner receipt, Management Oweru receipt, official EFD/VFD records,
independent payment status, safe acknowledgements, financial idempotency, working-day
payout deadlines, due Celery task, Management paid/hold/release and narrow future
complaint-policy boundary. No electronic money movement exists.

## Prerequisite fixes

* Actual current-phone confirmation now satisfies the previously unavailable
  activation gate; identity and required photos still apply.
* Oweru-only owner/phone confirmation outbox supports random hashed validation,
  seven-day configurable expiry, current price/rate/payment context, sent metadata,
  recipient, decision IP/browser and single use. Agent responses never contain tokens.
* Listing service freezes the published rate; database rejects reassignment.
  Existing NULL-rate Listings cannot be given a fabricated historical rate or close.
* Explicit verified-lister permission onboarding command bridges operational setup
  through the existing permission-bearing assignment helper, without automatic
  mirroring or request-time permission fallback.
* Existing private storage now has an S3-compatible adapter; its credentials/bucket
  configuration remain external. Tests use in-memory storage and mocked S3 calls.

## Requirement traceability

All domain event names below use the existing AuditLog service. Permission-bearing
assignment onboarding retains its existing legacy role audit stream.

| Requirement | Models / service | Permission and object policy | API | Audit | Tests |
|---|---|---|---|---|---|
| LEAD-01 sources/contact | Lead; create_lead; FinancialNotice | lead.create, eligible listing, own snapshot or own-lister customer | POST leads/ | lead.created; notice intent | test_interest_sources; test_external_customer_snapshot_and_metrics |
| LEAD-02 stages/notes/follow-up | LeadTransition/LeadNote; LeadTransitionService/add_note/set_follow_up | lead.update + own lister | transition/notes/follow-up | transitioned/lost/note_added/follow_up_changed | test_pipeline_history_notes_followup; test_forbidden_transition; test_lost_reason_and_terminal; audit rollback |
| LEAD-03 Closing | OwnerContact/Deal; DealClosingService | lead.update + deal.update + own matching lister | transition CLOSING | under_offer/final_price_recorded | test_closing_prerequisites; test_closing_duplicate_and_rollback; test_concurrent_closing |
| LEAD-04 frozen Deal/instructions | Deal; CommissionService; instructions; FinancialNotice | Deal buyer payment.submit_proof; closing lister policy | deals/payment instructions | deal.created; commission.calculated | test_end_to_end_acceptance; test_api_full_acceptance |
| LEAD-05 strict Won | Deal agreement; PaymentConfirmation; complete_deal | lister deal.update; Management payment.confirm | agreement upload/confirm/approve; complete | agreement.*; deal.completed; lead.transitioned; listing.sold | test_security; both acceptance tests; test_completion_rollback_and_payout_constraint |
| LEAD-06 private customers | derived Leads/Notes; CustomersView | lead.view + own lister | customers | private access policy | Lead object-scope test; customer/notes test |
| LEAD-07 pipeline performance | Lead/Transition; MetricsView | lead.view scoped lister/Management | metrics | read-only derived data | test_external_customer_snapshot_and_metrics; public views deferred |
| LEAD-08 Lost/sold review | LostLeadReview; review_lost_sales/task | internal completed-sale policy; no punishment | background boundary | lead.lost_sale_flagged | test_lost_sold_review |
| PAY-01 published versions | RateTable/RateBand; save_rate_draft/publish_rate_table | commission.manage + operational Management | rate-table draft/detail/publish | draft_saved/published | test_rate_draft_api_and_immutable_publish; overlap/gap; database guards |
| PAY-02 table visibility | RateTable; current_rate_table | commission.view; draft Management only | current/historical table GET | no mutation | rate API visibility test |
| PAY-03 formulas/freezing | Deal stored breakdown; CommissionService/reprice | deal.update + lister, no activity; rate-version guard | closing/final-price | calculated/recalculated | owner_formula_and_rounding; historical_version; freezes_on_activity; guards; publication concurrency |
| PAY-04 bank capture | BankAccount/OwnerContact; bank and token services | own lister or owner token; current context | bank-account/confirmation decision | bank_account.updated; confirmation.decided | bank idempotency/privacy; changed/expired owner context |
| PAY-05 privacy | dedicated bank serializers; bank snapshots | holder, Management payment.confirm, OPEN Deal buyer | bank/instructions only | sensitive_data.accessed | test_security; private documents; bank snapshot privacy |
| PAY-06 instructions/reference | Deal snapshots/reference; instructions | payment.submit_proof + Deal buyer | instructions | sensitive_data.accessed | exact reconciliation; both acceptance tests |
| PAY-07 proof | PaymentProof/Media; submit_proof | payment.submit_proof + buyer | proofs/document access | payment.proof_submitted | proof replay/conflict/retry; MIME tests; concurrency; private paths |
| PAY-08 owner receipt | PaymentConfirmation/Delivery; confirm_receipt/decide | authenticated owner deal.update or sent valid owner token | owner confirm/token decision | payment.owner_confirmed | authenticated owner test; external replay/conflict/security |
| PAY-09 Oweru receipt | PaymentConfirmation; confirm_receipt | payment.confirm + operational Management | confirm/oweru | payment.oweru_confirmed | API HTTP409; inactive/category/revocation; concurrent same key |
| PAY-10 payout | Payout; create_payout/working_deadline/mark_due_payouts/payout_action | payout.record + Management; own agent read | payouts/actions/history | created/due/paid | exact amount; working days; duplicate paid; concurrent completion/paid/due |
| PAY-11 official receipts | OfficialTaxReceipt/Media; record_tax_receipt/FinancialNotice | payment.confirm + Management | tax-receipt | official_receipt.recorded; acknowledgement intent | duplicate receipt tests; non-tax text in notices/instructions |
| PAY-12 complaint/manual holds | PayoutBlock; set_complaint_block/payout_action | complaint.handle or payout.hold + Management | hold/release + service boundary | held/released | test_payout_holds_working_days |
| Financial idempotency | IdempotencyRecord; execute | replay reauthorizes action/object; actor/op/resource key scope | financial Idempotency-Key | first mutation only | proof/confirm/receipt/payout replay; failed retry; isolation; HTTP409; seven concurrency cases |

## Financial acceptance evidence

Agent O=100,000,000, S=120,000,000, T=10%, X=3%:
owner 90,000,000; Oweru collects 30,000,000; Oweru retains 3,000,000;
agent payout 27,000,000. Owner S=100,000,000, X=3%:
owner 97,000,000; Oweru 3,000,000. Both exact values and the two reconciliation
invariants are asserted in executed tests.

## Idempotency and transaction architecture

Unique `(actor_scope, operation, resource, key)`; SHA-256 canonical logical request
fingerprint; file content digest; stored safe JSON result. Required header on
financial APIs; HTTP200 original result for successful equal replay; HTTP409 for
changed payload. Actor/resource/operation isolation is tested. No sensitive raw
request body is retained. Result, mutation and existing audit writes share one
transaction; failed claims disappear with rollback, allowing retries. No persistent
IN_PROGRESS row can strand a key after process failure. Successful records have
no automatic expiry; future retention must preserve deduplication guarantees.

The common Deal row lock serializes financial changes before key lookup/claim.
Closing locks Listing/Lead and database uniqueness prevents duplicate Deals;
completion locks Deal/Listing/Lead and creates the unique payout atomically.
PostgreSQL advisory transaction locking serializes rate publication and Listing
creation. Published rates, Listing version, activity-started Deal figures, bank
snapshots and payout amounts have direct-database guards.

Equal natural duplicates with different keys do not duplicate proofs,
confirmations, receipts, payouts or corresponding audits. Authenticated requests
and original-token replays are reauthorized before returning stored results.
External consumed tokens cannot execute another key. Storage failure/audit rollback
deletes newly uploaded private objects in the tested ordinary failure path.

## Security and deferred integrations

Object tests deny other buyers' Deals and other listers' Leads. Agents cannot
retrieve owner bank details or buyer slips through generic listing/media access.
Buyers cannot complete or confirm Oweru money. Clients cannot supply commission or
payout amounts or directly set WON. Owner tokens require Oweru staff sending,
current context and expiry; sensitive reads are audited. Bank snapshots/keys are
absent from generic serializers. Revocation and persisted inactivity stop access.

M09/public-view event collection, full M14–M26, verification ordering/PAY-13,
automatic fiscal integration/PAY-14, bilingual/email notification infrastructure,
full M20 and dual-store consolidation are deferred. Financial activity cancellation
and production storage-orphan lifecycle need separately reviewed policies. Existing
NULL-rate historical listings cannot be assigned invented rates. SRD specifies
residual reconciliation but no half-tie convention; the explicit Decimal
ROUND_HALF_UP policy is documented, with invalid negative residuals rejected.
Bank-access conflict is resolved by the user's explicit PAY-05 rule. Other
Management-title/anonymous-complaint conflicts are outside this implementation.

API keys/credentials are configured later; they are not embedded in source or
needed for phase-one manual bank tracking. Production private bucket configuration,
confirmation URL, published business rates, verified lister action onboarding,
actual staff sending and Celery scheduling remain operational setup.

## Database, audit, API and files

`M10_M13_BACKEND.md` provides the complete API route inventory, new models,
constraints/indexes, ten forward migrations, audit event list, privacy policy,
payout integration contract and idempotency retention/retry/concurrency semantics.
Existing historical migrations and original tests are unchanged.

## Final executed validation

| Execution | Collected | Passed | Failed | Skipped | Deselected |
|---|---:|---:|---:|---:|---:|
| Complete PostgreSQL/PostGIS suite | 1125 | 1125 | 0 | 0 | 0 |
| Dedicated PostgreSQL concurrency suite | 7 | 7 | 0 | 0 | 0 |
| Dedicated end-to-end acceptance selection | 22 | 2 | 0 | 0 | 20 |

The complete suite finished in 82.08 seconds. It contains the original 1070 tests
and 55 added tests, including seven concurrency and two end-to-end tests; subset
counts above are not additive. Normal non-concurrency tests account for 1118
passes within the complete execution. All tests ran against isolated PostgreSQL/
PostGIS, not SQLite. The dedicated concurrency execution finished in 10.75 seconds;
the end-to-end selection finished in 7.75 seconds.

Django system checks: no issues. Forward migration application: succeeded.
`makemigrations --check --dry-run`: no changes detected. `git diff --check`: passed.
No frontend files, existing migrations, original tests, secrets, environment files,
payment evidence, database dumps or local database files were added/modified.
Live production S3 and delivery services were not exercised; keys remain for later
configuration. Their mocked adapter tests are included in the suite.

## Final Git state

`git diff --stat` (tracked changes only; new untracked files are listed below):

```text
 README.md                         |  5 +++++
 backend/apps/listings/models.py   |  1 +
 backend/apps/listings/services.py | 19 ++++++++++++++++++-
 backend/apps/media/storage.py     | 34 ++++++++++++++++++++++++++++++++++
 backend/config/api_urls.py        |  7 +++++++
 backend/config/settings/base.py   | 11 ++++++++++-
 6 files changed, 75 insertions(+), 2 deletions(-)
```

`git status --short`:

```text
 M README.md
 M backend/apps/listings/models.py
 M backend/apps/listings/services.py
 M backend/apps/media/storage.py
 M backend/config/api_urls.py
 M backend/config/settings/base.py
?? backend/apps/commissions/
?? backend/apps/deals/
?? backend/apps/leads/
?? backend/apps/listings/migrations/0003_listing_rate_table.py
?? backend/apps/payments/
?? docs/M10_M13_BACKEND.md
?? docs/M10_M13_DELIVERY_REPORT.md
?? docs/M10_M13_INVESTIGATION.md
```

The six modified files are the tracked paths above. No files were staged,
committed or pushed. The following inventory lists every new file.


Created files (62):

- `backend/apps/commissions/__init__.py`
- `backend/apps/commissions/apps.py`
- `backend/apps/commissions/migrations/0001_initial.py`
- `backend/apps/commissions/migrations/__init__.py`
- `backend/apps/commissions/models.py`
- `backend/apps/commissions/serializers.py`
- `backend/apps/commissions/services.py`
- `backend/apps/commissions/urls.py`
- `backend/apps/commissions/views.py`
- `backend/apps/deals/__init__.py`
- `backend/apps/deals/apps.py`
- `backend/apps/deals/migrations/0001_initial.py`
- `backend/apps/deals/migrations/0002_initial.py`
- `backend/apps/deals/migrations/0003_deal_bank_snapshots.py`
- `backend/apps/deals/migrations/0004_deal_cancelled_state.py`
- `backend/apps/deals/migrations/__init__.py`
- `backend/apps/deals/models.py`
- `backend/apps/deals/serializers.py`
- `backend/apps/deals/services.py`
- `backend/apps/leads/__init__.py`
- `backend/apps/leads/apps.py`
- `backend/apps/leads/migrations/0001_initial.py`
- `backend/apps/leads/migrations/__init__.py`
- `backend/apps/leads/models.py`
- `backend/apps/leads/policies.py`
- `backend/apps/leads/serializers.py`
- `backend/apps/leads/services.py`
- `backend/apps/leads/tests/__init__.py`
- `backend/apps/leads/tests/test_leads.py`
- `backend/apps/leads/urls.py`
- `backend/apps/leads/views.py`
- `backend/apps/listings/migrations/0003_listing_rate_table.py`
- `backend/apps/payments/__init__.py`
- `backend/apps/payments/apps.py`
- `backend/apps/payments/confirmations.py`
- `backend/apps/payments/documents.py`
- `backend/apps/payments/idempotency.py`
- `backend/apps/payments/management/__init__.py`
- `backend/apps/payments/management/commands/__init__.py`
- `backend/apps/payments/management/commands/enable_marketplace_lister_actions.py`
- `backend/apps/payments/migrations/0001_initial.py`
- `backend/apps/payments/migrations/0002_financial_guards.py`
- `backend/apps/payments/migrations/0003_financial_notice.py`
- `backend/apps/payments/migrations/__init__.py`
- `backend/apps/payments/models.py`
- `backend/apps/payments/notices.py`
- `backend/apps/payments/onboarding.py`
- `backend/apps/payments/serializers.py`
- `backend/apps/payments/services.py`
- `backend/apps/payments/tasks.py`
- `backend/apps/payments/tests/__init__.py`
- `backend/apps/payments/tests/conftest.py`
- `backend/apps/payments/tests/test_api_workflow.py`
- `backend/apps/payments/tests/test_concurrency.py`
- `backend/apps/payments/tests/test_integrations.py`
- `backend/apps/payments/tests/test_safety.py`
- `backend/apps/payments/tests/test_workflow.py`
- `backend/apps/payments/urls.py`
- `backend/apps/payments/views.py`
- `docs/M10_M13_BACKEND.md`
- `docs/M10_M13_DELIVERY_REPORT.md`
- `docs/M10_M13_INVESTIGATION.md`
