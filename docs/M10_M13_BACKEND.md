# Marketplace M10–M13 backend

Authority: Marketplace SRD v1.3, especially LEAD-01–08, PAY-01–12 and sections
9.1, 9.3, 9.5 and 20.3. PAY-05 is the restrictive bank privacy rule, as expressly
directed for this implementation. This backend records bank transfers; it never
moves funds, maintains wallets or calls a payment gateway.

## Authorization and existing work

M04–M08 retains its existing canonical-role behavior. No assignments or historical
authorization migrations were rewritten. New action gates use only
`User.has_marketplace_permission`, backed by `apps.roles.legacy_authorization`
(app label `authorization`). Canonical roles are not an alternative grant source.
Every new protected service additionally checks an active persisted actor and
object participation. Public/operational compatibility remains enforced by the
permission-bearing store. Django superuser status grants no Marketplace bypass.

The dual stores are technical debt for a separately reviewed future consolidation.
Canonical-only listers intentionally cannot call the new protected actions.
For existing verified listers, explicit Management onboarding is available:

```text
python manage.py enable_marketplace_lister_actions --manager-id UUID --lister-id UUID --role agent
```

This command requires the Management actor's `authorization.assign_role`, a public
active target, the matching canonical lister relationship and approved unexpired
ListerIdentity. It creates/reactivates the one permission-bearing assignment
through its existing category/audit helper. It does not mirror stores automatically,
grant from a canonical role at request time, change category or bypass revocation.

Lister Lead actions require `lead.view`/`lead.update` plus ownership; Management
can read Leads with `lead.view`. Customer lists always belong to the requesting
lister, including when Management invokes that endpoint. Buyers use
`payment.submit_proof` plus Deal participation for their payment-context Deal
reads. This does not invent a Buyer `deal.view` grant. Listers use `deal.view` plus
participation. Management reads use `deal.view` and the effective operational
Management role. Management mutations require the exact action grant, not merely
the role. Inactive accounts and revoked assignments cannot mutate or replay.

## M10 Leads

Authenticated interest creates a NEW Lead for ENQUIRY, WHATSAPP_CONTACT or
VIEWING_REQUEST, copying the buyer account's name/WhatsApp and retaining listing,
property and lister references. A lister can record their own external customer's
name and WhatsApp; account association is resolved by the registered account's unique
phone context, never a client-supplied buyer UUID. Closing requires a registered
active buyer, so an unregistered customer remains a Lead until account onboarding.

The forward pipeline is NEW → CONTACTED → VIEWING → NEGOTIATION → CLOSING.
Only internal Deal completion writes WON. LOST needs a reason. Stage history
records previous/new stages, actor, reason and timestamp. Notes and follow-up
changes have dedicated actions; generic stage PATCH is unavailable. Private notes
are returned only in authorized lister/Management Lead context.

An unpaid Closing can become LOST atomically: retain the CANCELLED Deal snapshot
and release the Listing to ACTIVE. A Deal with proof, confirmation or agreement
activity cannot be reversed through this Lead action. Refund/dispute cancellation
requires a future reviewed policy; no financial reversal is invented here.

Customers derive from own Leads with private notes. Metrics expose enquiries,
viewings, reached-stage conversion, response time and Won counts, with optional
listing filtering. Public-view counts remain explicitly unavailable until the
M09/M24 event source is connected; this does not implement M09.

Completed sales match LOST Leads for the same property and buyer in the previous
`LEAD_LOST_REVIEW_MONTHS` (default six calendar months). A unique LostLeadReview
flags Management review; no punishment, reversal or automatic adjudication occurs.
The repeated Celery `lost_sold_review` job is safe to rerun.

## M11 Closing and agreements

DealClosingService locks the Listing, then Lead. It requires Negotiation, an active
Listing, matching property/lister, an active registered buyer/lister, valid final
price, the Listing's published historical rate version and receiving bank accounts.
Agent listings additionally require the owner to have confirmed the current owner
price and provided their bank account through a secure Oweru-delivered link.

Lead CLOSING, Listing UNDER_OFFER, Deal snapshot, commission fields, notices and
audit writes share one transaction. A unique Deal per Lead and one OPEN Deal per
Listing supplement row locks. A repeated equal-price Closing returns the same Deal;
a changed-price duplicate must use the explicit repricing action. A cancelled Deal
cannot reopen through Closing. Different Leads cannot race to offer one Listing.

Deal snapshots retain participants/contact, property/listing, kind, prices, rate
version/band/rates, four whole-shilling amounts, unique Oweru reference and private
receiving-bank snapshots. Bank snapshots never appear in generic Deal serializers.

Agreement upload uses a private Media object owned by Deal. The lister explicitly
confirms the signed agreement states the exact final price. Management explicitly
verifies/approves that price under `payment.confirm`. Replacement clears lister
confirmation; an approved agreement cannot be replaced. This is a document review
workflow, not cryptographic signature verification.

Completion requires owner receipt, Oweru receipt, uploaded signed agreement, lister
exact-price confirmation and Management price approval. COMPLETE, WON, SOLD,
unique agent payout creation and Lost review are atomic. Buyers cannot complete;
direct WON requests are rejected. No agent payout is created for owner Deals.

## M12 Rates and money

Management saves draft RateTable versions and their bands, then publishes them.
Published versions and bands are immutable, including PostgreSQL direct updates
and deletes. Bands are inclusive whole-shilling intervals: the next lower bound
must equal previous upper + 1. Coverage starts at zero and finishes with one
unbounded upper range. Bounds/rates have constraints; publication validates full
coverage and Oweru rate + agent rate = total rate, including a database guard.

No permanent final table is hardcoded or silently published. Management must
publish the configured version before financial-workflow Listing creation.
Current and historical published tables are readable by authorized listers.

Creation through the existing Listing service freezes the currently published
version. PostgreSQL transaction advisory locking serializes rate publication
with creation-time rate selection, preventing a publication/creation timing race.
Existing pre-M12 Listings retain NULL rather than being assigned a
fabricated historical version. Canonical-only legacy draft creation remains
compatible with M04–M08. Such a NULL-rate Listing cannot activate after phone
confirmation or enter Closing. Recreate it through the normal service after rate
publication; there is no silent backfill or rate reassignment endpoint.
The PostgreSQL guard rejects later Listing rate-version changes, including NULL
to another version. The final selling price selects the band at Closing.

All calculations live in CommissionService and use Decimal. Money inputs reject
floats, fractions, NaN/infinity, nonpositive or out-of-range values. Agent formula:

```text
owner transfer = O × (1 − T)
Oweru transfer = (S − O) + O × T
Oweru retained = O × X
agent payout = O × (T − X) + (S − O)
```

For owner listings O = S, owner transfer = S × (1 − X), Oweru transfer/retained =
S × X and agent payout = 0. SRD specifies whole TSh and residual allocation to
Oweru, but does not specify a half-tie rule. This implementation uses Decimal
ROUND_HALF_UP for rounded owner transfer and agent payout, derives Oweru transfer
as S minus owner transfer, and retained as Oweru transfer minus agent payout.
Both sums therefore reconcile exactly. A negative retained residual is rejected
before Closing rather than creating an invalid negative financial record.

Acceptance values:

| Scenario | Owner transfer | Oweru transfer | Oweru retained | Agent payout |
|---|---:|---:|---:|---:|
| O=100,000,000; S=120,000,000; T=10%; X=3% | 90,000,000 | 30,000,000 | 3,000,000 | 27,000,000 |
| Owner S=100,000,000; X=3% | 97,000,000 | 3,000,000 | 3,000,000 | 0 |

Only changed final price before any financial or agreement activity can reprice.
Rate version never changes. Proof, receipt confirmation, tax receipt, agreement
or completed state freezes the breakdown; PostgreSQL guards protect direct edits
as well as service checks. Historical API reads use stored amounts.

## M13 Bank transfers and private evidence

PAY-05 bank information is shown only to its holder, authorized Management or the
buyer of an OPEN Deal through dedicated payment instructions. Agents have no
generic access to their external owner's bank. Owner and Oweru bank details are
snapshotted at Closing so later account updates cannot alter issued instructions.
Instructions use the frozen two amounts and unique OWR payment reference.

Buyer proofs are PDF/JPEG/PNG with matching extension, content detection and MIME,
bounded by `MEDIA_MAX_UPLOAD_BYTES`. Proof, agreement, tax receipt and payout proof
use the existing private storage abstraction with Deal-specific authorization.
Generic media access continues to deny financial Media. Responses return safe IDs
or short-lived signed URLs, never object keys. Listers cannot retrieve buyer bank
slips merely because they listed the property.

Owner listings use authenticated receipt confirmation by the owner. Agent-owner
receipts use purpose/context-bound random single-use tokens with hashed validation,
configurable seven-day expiry, recipient, sent actor/time and decision IP/browser.
Links are visible only in Oweru Management's outbox; Agent request responses contain
only delivery IDs/status. Unsent links cannot be used. Owner and Agent numbers must
differ; shared owner numbers across Agents generate an audit review flag.
Phone confirmation uses the same narrow outbox boundary and matches the current
account phone. Actual phone confirmation satisfies the pre-existing activation
gate; the gate is not removed or faked. Explicit staff sending/marking is required.

Independent confirmations avoid a false linear payment state: AWAITING_PAYMENT,
PROOF_UPLOADED, OWNER_CONFIRMED, OWERU_CONFIRMED, BOTH_CONFIRMED (agreement pending),
COMPLETE. Oweru confirmation requires operational Management and payment.confirm;
amount comes from the frozen Deal and the bank reference is recorded.

Official receipts record the externally issued EFD/VFD number and private copy,
with a unique number and one receipt per Deal. There is no TRA/VFD provider call.
The acknowledgement notice expressly says “This is not a tax receipt”.

FinancialNotice records transactional manual WhatsApp delivery intents for new
Leads, instructions, the full-check offer and non-tax acknowledgement. Management
retrieves click-to-chat messages and marks them sent. This and ConfirmationDelivery
are the minimum financial outbox boundaries, not a full M21 notifications platform.
Actual sending remains manual; queued notices are not claimed to have been sent.

## Idempotency contract

`Idempotency-Key` is mandatory for financial API actions, including Closing,
financial Lead cancellation, repricing, agreement actions, proofs, owner/Oweru
confirmation, official receipt, completion, bank updates and payout mutations.
Keys must be nonempty and at most 128 characters. Nonfinancial notes/follow-up
and manual notification sent markers do not require this header.

IdempotencyRecord uniqueness scopes actor identity + operation + resource UUID +
key. External decisions use `delivery:UUID` as the authenticated token principal.
The same text key for another actor, Deal or operation does not replay another
request. Canonical JSON (sorted keys, normalized validated values) is SHA-256
fingerprinted; uploaded files use content SHA-256 and logical transfer context.
Filenames and multipart encodings do not change a logical file request.
Raw request bodies/bank payloads are not stored in the idempotency table.

The stable business resource is locked before looking up/claiming a key. Deal
mutations share the same Deal row lock; Closing uses the Listing/Lead lock; bank
updates use the holder row. Reauthorization runs before both mutation and replay.
One transaction contains business mutation, existing AuditLog writes and successful
idempotency result. No committed IN_PROGRESS/FAILED claim is used. Process failure
or rollback removes unsuccessful records, allowing retry. Same key/same fingerprint
returns the original stored successful result with HTTP 200. Same key/changed
fingerprint returns HTTP 409. Replay emits no business audit, upload or mutation.

Different-key duplicate proofs (same Deal/transfer/digest), confirmations, receipt
and payout creation/payment also return existing equal records without duplicate
audits; conflicting receipt/payment evidence is rejected. Consumed external owner
tokens cannot execute a new key; the original valid-key replay is permitted until
the link expires. Missing/invalid/expired tokens never grant access to stored results.

Successful records currently have **no automatic deletion or expiry**: retain
them alongside the financial history to prevent delayed duplicate execution.
A future archival policy must preserve replay/deduplication guarantees.
Stored results contain safe IDs/context, not private storage keys or bank accounts.

Private object storage is not transaction-aware. The wrapper deletes newly stored
objects on ordinary mutation/audit failure. Process termination between upload and
database commit can still leave an inaccessible orphan; production storage needs
an orphan lifecycle/reconciliation policy. No orphan is exposed as a successful
financial record. Failed object deletion requires operator/storage reconciliation.

## Payouts and future complaints

Completion creates one PENDING agent payout from frozen Deal.agent_payout. Deadline
defaults to three working days in Africa/Dar_es_Salaam, excluding weekends and
optional configured holiday dates (`PAYOUT_HOLIDAYS`). Management can pay before
the deadline; DUE means the deadline has arrived. The rerunnable Celery
`payout_due_check` serializes with other Deal mutations and emits one change event.

Management records bank reference/proof, never a client-supplied amount. Agent reads
are restricted to their own status/history. ON_HOLD carries a manual reason.
PayoutBlock is the narrow M20 policy boundary. M20 must call
`set_complaint_block(actor, deal_id, external_reference, is_open, key)` when an
applicable complaint opens/closes. The integration requires authorized Management
`complaint.handle`, locks the Deal, has unique complaint references and is idempotent.
Open blocks hold payouts and prevent both payment and release. Closing one complaint
does not remove another open block or automatically release a manual hold.
No full Complaint subsystem or complaint-adjudication endpoint exists here.

## API inventory

All paths below are relative to `/api/v1/`. Protected APIs use existing JWT/DRF
defaults. External confirmation decisions use only the bearer confirmation token,
are anonymous by account design, and have a dedicated IP rate limit.

| Path | Methods / action |
|---|---|
| leads/ | GET scoped list; POST interest/customer |
| leads/customers/ | GET own private customers |
| leads/metrics/ | GET scoped pipeline metrics |
| leads/{id}/ | GET private detail/notes/history |
| leads/{id}/transition/ | POST validated stage; financial stages require key |
| leads/{id}/notes/ | POST private note |
| leads/{id}/follow-up/ | POST follow-up timestamp/null |
| deals/; deals/{id}/ | GET role-specific scoped financial read |
| deals/{id}/final-price/ | POST changed pre-activity price; key |
| deals/{id}/agreement/upload,confirm,approve/ | POST file or explicit exact-price boolean; key |
| deals/{id}/complete/ | POST Management completion; key |
| deals/{id}/documents/{media_id}/ | GET authorized signed URL |
| commissions/rate-tables/ | GET current; POST Management draft |
| commissions/rate-tables/{id}/ | GET authorized version; PUT Management draft |
| commissions/rate-tables/{id}/publish/ | POST immutable publication |
| payments/bank-account/ | GET holder; PUT lister bank; key on PUT |
| payments/confirmation-requests/ | POST PHONE, OWNER_PRICE, OWNER_RECEIPT intent; no bearer token returned |
| payments/confirmations/{id}/ | GET token context; POST Confirm/Decline with key |
| payments/deals/{id}/instructions/ | GET OPEN-Deal buyer instructions |
| payments/deals/{id}/proofs/ | POST transfer + file; key |
| payments/deals/{id}/confirm/owner,oweru/ | POST authenticated permitted receipt; key |
| payments/deals/{id}/tax-receipt/ | POST EFD/VFD number + file; key |
| payouts/ | GET own-agent or authorized Management list |
| payouts/deals/{id}/history/ | GET authorized payout history |
| payouts/deals/{id}/create,hold,release,paid/ | POST Management action; key |
| management/finance/outbox/ | GET protected confirmation links/context |
| management/finance/outbox/{id}/sent/ | POST explicit staff-sent marker |
| management/finance/notices/ | GET manual financial notice messages |
| management/finance/notices/{id}/sent/ | POST explicit staff-sent marker |
| management/finance/banks/{id}/ | GET authorized sensitive bank review |
| management/finance/oweru-bank/ | PUT Oweru receiving bank; key |

Financial unknown fields are rejected, including calculated commissions, payout
amounts, direct WON/COMPLETE flags and raw storage keys. Agreement confirm/approve
bodies require `confirms_exact_final_price: true`. Completion is a separate action,
so confirmations alone cannot silently sell the property before agreement review.

## Audit events

Existing AuditLog records: lead.created, lead.transitioned, lead.lost,
lead.note_added, lead.follow_up_changed, lead.lost_sale_flagged,
listing.under_offer, listing.sold, listing.offer_released, listing.suspended,
deal.created, deal.final_price_recorded, deal.completed, deal.cancelled,
commission.calculated, commission.recalculated, rate_table.draft_saved,
rate_table.published, agreement.uploaded, agreement.price_confirmed,
agreement.approved, payment.proof_submitted, payment.owner_confirmed,
payment.oweru_confirmed, official_receipt.recorded, payout.created, payout.due,
payout.held, payout.released, payout.paid, bank_account.updated,
confirmation.queued, confirmation.sent, confirmation.decided,
owner_contact.shared_number_flagged, financial_notice.sent and
sensitive_data.accessed. Authorization onboarding reuses the existing legacy
role.assigned audit stream, without creating a third audit mechanism.

## Database and operations

New models: Lead, LeadTransition, LeadNote, LostLeadReview; Deal; RateTable,
RateBand; OwnerContact, BankAccount, ConfirmationDelivery, PhoneConfirmation,
PaymentProof, PaymentConfirmation, OfficialTaxReceipt, IdempotencyRecord,
Payout, PayoutBlock, FinancialNotice. Modified model: Listing.rate_table.

New migrations: leads.0001_initial; deals.0001_initial/0002_initial/
0003_deal_bank_snapshots/0004_deal_cancelled_state; commissions.0001_initial;
listings.0003_listing_rate_table; payments.0001_initial/0002_financial_guards/
0003_financial_notice. Existing migration files are unchanged.

Uniqueness: Deal per Lead; OPEN Deal per Listing; Deal payment reference; rate
version; band lower bound per version; user/owner-contact bank; singleton Oweru
bank; one phone confirmation per user; proof digest per Deal/transfer; confirmation
per Deal/transfer; official receipt per Deal and globally unique number; payout per
Deal; lost-lead/sold-deal review; actor/operation/resource/key; complaint policy
reference per Deal; Lead/Deal notification intent per recipient/purpose.
Checks cover valid sources/stages/states/transfers, required Lead contacts,
positive prices, nonnegative payouts/transfers, exact two financial reconciliations,
rate bounds/ranges and exclusive bank holder. Indexes cover lister pipeline,
Lost property/buyer, Deal buyer/lister states, rate publication and payout deadlines,
alongside UUID/FK/unique indexes.
PostgreSQL triggers additionally protect published tables/bands, full coverage at
publication, Listing version, Deal financial/bank snapshots and payout amount.

Configure external credentials later through environment/provider-chain settings.
`MEDIA_STORAGE_BACKEND=s3` uses the existing S3-compatible private storage adapter;
set bucket/endpoint and provider credentials outside Git, enforce bucket public
access blocking and use HTTPS. Tests use in-memory private storage. Set
`OWNER_CONFIRMATION_URL` before actual link delivery. No API keys are necessary
for phase-one manual WhatsApp/bank tracking. Configure Celery scheduling for the
two financial tasks; the functions can be invoked safely by existing workers.

## Deferred and unresolved boundaries

* No M09, frontend, full M14–M26, wallet/custody/automatic transfer, TRA integration
  or full Complaint/notification implementation.
* Full-check offer notice exists; ordering/payment/verification execution remains
  M14+/PAY-13. Automatic official receipts remain PAY-14.
* Generic view analytics, bilingual notification templates/email dispatch and
  production scheduler/storage/account configuration remain integrations.
* Paid/partially paid cancellation/refund rules are not specified sufficiently for
  a safe financial reversal and are rejected through the Lead LOST action.
* SRD's half-tie rounding rule is unspecified; the documented exact Decimal policy
  and residual reconciliation are tested. Unrepresentable negative residuals reject.
* Pre-M12 Listings cannot acquire an invented historical rate version.
* Director/Head-of-Operations naming conflicts and anonymous complaint rules remain
  outside scope; no new roles are introduced. PAY-05 bank-access conflict is resolved
  by the user's explicit restrictive rule for this implementation.
* Dual-store authorization consolidation and inaccessible storage-orphan cleanup
  remain separately reviewed operational/architecture work.

Validation results are recorded in the final work report, not inferred from models
or endpoint existence. PostgreSQL tests are required for row locks and triggers.
