# Roadmap: the remaining phases

What is left to build for the Phase 1 launch, in order, with the user flow, screens, endpoints and finish line of each phase. Requirements are in [srd.md](srd.md); what already exists is in [architecture.md section 10](architecture.md#10-status-by-module).

Last updated: 21 October 2026.

| Phase | Area | Status |
|---|---|---|
| 1 | Deals and money | **In progress: step 2 (references board)** |
| 2 | Partner work: site capture and verification tasks | Not started |
| 3 | Partner management: local officials and professionals | Not started |
| 4 | Rest of the full check | Not started |
| 5 | Management administration | Not started |
| 6 | Smaller public and lister screens | Not started |
| 7 | Backend gaps | Not started |
| 8 | Launch readiness | Not started |

Why this order: a sale cannot reach Won without Phase 1, and a full check cannot finish without Phases 2 to 4. Management administration (Phase 5) is needed before launch but nothing else depends on it.

## How every phase runs

Each phase goes through the same seven steps. The status table above names the step a phase is on.

1. **Contract check.** Read the SRD requirements and the backend endpoints for the phase. List anything the backend is missing or gets wrong, and fix it in the backend with tests (allowed when a screen needs it).
2. **References board.** Collect Dribbble and Pinterest references for each screen family and publish a picking board ([design.md section 10](design.md#10-designing-a-new-screen)).
3. **Pick.** The product owner picks, or approves the recommended picks.
4. **Build.** Screens matching the picks, on the existing components, in both languages, behind the right permissions.
5. **Verify.** Type check, lint, backend tests against the baseline, and the flow walked through in a browser at phone and desktop width, in Swahili and English.
6. **Docs.** Update [architecture.md section 10](architecture.md#10-status-by-module), this file, and any convention that changed.
7. **Push and merge.** Merge `origin/main`, re-check, fast-forward `main`, push.

---

## Phase 1: Deals and money

**Goal:** a sale goes from Closing to Won inside the system, the buyer knows exactly what to pay and where, management confirms Oweru's money, and the agent is paid and can see it.

**Requirements:** LEAD-03, LEAD-04, LEAD-05, LST-09, PAY-01 to PAY-12, CMP-06 (payout hold shown), NTF 20.4 (payment instructions, payout paid).

**Already built:** the lister moves a lead to Closing with the final price (`POST leads/{id}/transition/`, which creates the Deal). Owner price and money-received confirmation links for agent listings (`/confirm`).

### Flow: agent listing

1. Management publishes a rate table and sets Oweru's receiving bank account (once, before any agent listing).
2. The agent sees the rate table and a live payout preview while entering prices on the listing form.
3. The agent saves their own bank account for payouts.
4. The owner confirms their price and bank account through the WhatsApp link (built).
5. The lister moves the lead to Closing with the final price (built). The Deal is created with the frozen breakdown and a payment reference.
6. The buyer opens **My purchases**, sees two transfers (owner's account, Oweru's account with the reference), pays at the bank and uploads a slip for each.
7. The owner confirms the money arrived through the WhatsApp link (built). Management confirms Oweru's money against the bank statement and records the bank reference.
8. The lister uploads the signed sale agreement and confirms it states the exact final price. Management checks and approves it.
9. Management records the official tax receipt number and copy.
10. Management completes the deal: the lead becomes Won, the listing Sold, and an agent payout is created (due in 3 working days).
11. Management pays the agent, records the bank reference and proof. The agent sees the payout as Paid. A complaint on the deal puts the payout on hold automatically.

### Flow: owner listing (no agent)

Same as above, except: no owner price or payout. The owner, who is the lister, confirms receipt of their own money in the deal page instead of through a link. Oweru's share comes from the same rate table.

### Screens

| Screen | Who | Route (proposed) | Endpoints |
|---|---|---|---|
| Deal page | Lister | `/lister/deals/:dealId` | `GET deals/{id}/`, `POST deals/{id}/final-price/`, `POST deals/{id}/agreement/upload/`, `.../agreement/confirm/`, `GET deals/{id}/documents/{media_id}/`, `POST payments/deals/{id}/confirm/owner/` (owner listings) |
| My deals | Lister | `/lister/deals` | `GET deals/` |
| Bank account | Lister | `/lister/bank` | `GET`/`PUT payments/bank-account/` |
| Rate table and payout preview | Lister | `/lister/rates`, inside the listing editor | `GET commissions/rate-tables/` |
| Payouts | Agent | `/lister/payouts` | `GET payouts/`, `GET payouts/deals/{id}/history/` |
| My purchases: instructions and slips | Buyer | `/purchases/:dealId` | `GET deals/{id}/`, `GET payments/deals/{id}/instructions/`, `POST payments/deals/{id}/proofs/`, `GET notifications/self-service/deals/{id}/` |
| Deals desk | Management | `/staff/deals` | `GET deals/` |
| Deal review | Management | `/staff/deals/:dealId` | `GET deals/{id}/`, `POST payments/deals/{id}/confirm/oweru/`, `POST deals/{id}/agreement/approve/`, `POST payments/deals/{id}/tax-receipt/`, `POST deals/{id}/complete/`, `GET management/finance/banks/{id}/` |
| Payouts desk | Management | `/staff/payouts` | `GET payouts/`, `POST payouts/deals/{id}/hold/`, `.../release/`, `.../paid/` |
| Rate tables | Management | `/staff/rates` | `GET`/`POST commissions/rate-tables/`, `PUT .../{id}/`, `POST .../{id}/publish/` |
| Oweru bank account | Management | inside Rate tables or settings | `PUT management/finance/oweru-bank/` |

All money actions send an `Idempotency-Key`. Bank details appear only on the holder's own screen, management review and the buyer's instructions (PAY-05).

### Step 1 findings (contract check)

Done 21 October 2026.

- The backend contract is in [M10_M13_BACKEND.md](M10_M13_BACKEND.md). All endpoints above exist.
- `GET deals/` and `GET deals/{id}/` serve the buyer too: buyers hold `payment.submit_proof` by default, and get `BuyerDealSerializer` (no lister-only fields). The audit records each detail read.
- Financial notices and confirmation deliveries already flow into the central WhatsApp outbox (`apps/notifications/signals.py`), so no separate finance outbox screen is needed.
- **Backend fix to make in step 4:** message links still point to `/api/v1/...` instead of frontend pages, the same fault fixed for complaints in `9d1215c`. Affected: new lead (`/lister/enquiries`), deal notices (the Phase 1 deal pages), payout paid (`/lister/payouts`), identity decision (`/lister/identity`), free check report (`/free-check/{id}?token=...`, page already exists). Verification task links follow in Phase 2.
- Listers with only canonical roles cannot call the protected money actions until Management runs `enable_marketplace_lister_actions` (M10_M13_BACKEND.md). The UI must explain this state rather than fail silently.

### Done when

- Both flows above can be walked end to end in the browser with test data, and the SRD 9.6 acceptance tests pass (including the worked example: 90,000,000 to the owner, 30,000,000 to Oweru, 3,000,000 kept, 27,000,000 to the agent).
- No bank detail is visible to anyone PAY-05 does not allow.

---

## Phase 2: Partner work (site capture and verification tasks)

**Goal:** local officials, professionals, owners and agents can do their part of a full check, and the verifier can assign and review it.

**Requirements:** FUL-03 to FUL-06, MAP-01 to MAP-06, MAP-08, MAP-09, LOC-02 to LOC-05, PRO-02 to PRO-05, VER-03, VER-04, VER-06.

### Flow

1. After consent, the verifier opens the full check workspace and creates tasks: site capture (owner, agent or surveyor), local office (routed automatically to the official for the street or village), professional tasks (chosen from eligible professionals for the district).
2. Each assignee gets an outbox WhatsApp alert and sees the task in their dashboard. Professionals accept or decline; a decline returns to the verifier. Conflicts of interest are blocked (VER-06).
3. **Site capture** on a phone: stand at each corner and tap Record (accuracy worse than 10 m is rejected), at least 3 corners, add photos and a walking video from the camera or gallery. The system computes area, compares with the stated size and tests overlaps.
4. **Local office task**: the official answers the five questions and uploads the signed and stamped confirmation.
5. **Professional task**: findings, report and evidence uploaded.
6. Submissions lock. Corrections are new versions. The verifier reviews each in the workspace with the map, satellite view and overlaps, then records the result (Phase 4 finishes the job).

### Screens

| Screen | Who | Endpoints |
|---|---|---|
| Site capture (phone-first) | Owner, agent, surveyor | `POST properties/{id}/site-captures/`, `site-captures/{id}/corners/`, `.../media/`, `.../submit/`, `GET site-captures/{id}/`, `.../assets/` |
| Official dashboard and task detail | Local official | `GET local-official/full-check-tasks/`, `local-official/me/`, `verification-tasks/{id}/`, `.../submit/`, `.../correction/` |
| Professional dashboard and task detail | Professional | `GET professionals/tasks/`, `professionals/me/`, `verification-tasks/{id}/decision/`, `.../submit/`, `.../declare-relationship/` |
| Task assignment in the full check workspace | Verifier | `GET full-checks/{id}/professionals/`, `POST verification-tasks/{id}/assign/`, `GET verification-tasks/`, `verification-tasks/submissions/{id}/report/`, `management/map-layers/` |
| Capture review (promote boundary) | Verifier | `POST site-captures/{id}/promote/` |

### Open questions for step 1

- How partners sign in for the first time (forced password change, ACC-06) and whether the frontend handles it.
- Whether the `verifications/.../field/` endpoints (lister field verification, official field review) are still part of the location check or an older path.

---

## Phase 3: Partner management

**Goal:** management builds and maintains the network of officials and professionals.

**Requirements:** LOC-01, LOC-06, LOC-07, PRO-01, SRD 14.2.

### Flow

1. Staff get an office's WhatsApp number through the ward or council, and send a registration link from the outbox.
2. The official registers: name, position, ID number, live photo, office locality, stamp photo.
3. The Head of Operations approves after confirming with the ward. The official can sign in, and waiting tasks appear.
4. Management deactivates officials who leave office and invites the replacement.
5. Management registers professionals (type, registration number, coverage); login details go out through the outbox.
6. A coverage map shows streets, villages and wards with active officials.

### Screens

| Screen | Who | Endpoints |
|---|---|---|
| Officials list, detail, approve, deactivate | Management | `management/local-officials/`, `.../{id}/`, `.../jurisdictions/`, `.../localities/`, `.../revoke/` |
| Official registration (from the WhatsApp link) | Official | To confirm in step 1: no self-registration route is visible in the API yet |
| Coverage map | Management | Built from officials' localities |
| Professionals list and form | Management | `management/professionals/`, `.../{id}/` |

---

## Phase 4: Rest of the full check

**Goal:** every full check path works, not only agent listings with an owner link.

**Requirements:** FUL-02, FUL-07, VER-05, VER-07.

### Flow additions

- Owner listings: the owner accepts or declines consent in their own account (`POST full-checks/{id}/owner-consent/`).
- Agent listings with no owner contact: the agent supplies it within 3 working days (`POST full-checks/{id}/owner-contact/`).
- The verifier starts the job once paid and consented (`POST full-checks/{id}/start/`).
- A buyer refreshes a check between 30 days and 6 months (`POST full-checks/{id}/refresh/`).
- Adverse results reach only the paying buyer and block Level 3, with no public label.

---

## Phase 5: Management administration

**Goal:** management can run the system without developer help.

**Requirements:** ADM-01 to ADM-05, LST-03, LST-12, NTF-04, NFR-12.

| Screen | Endpoints |
|---|---|
| Dashboard queues: identities, flagged listings, duplicates, partner approvals, tasks needing an official, payments to confirm, payouts due, complaints by status, outbox waiting | `GET management/dashboard/` |
| Settings with change history (including both full check scope languages and the fee) | `management/settings/`, `management/verification-settings/{key}/` |
| Audit log | `GET management/audit/` |
| Suspend and restore listings and accounts with a reason | `management/listings/{id}/suspend/`, `.../restore/`, `management/listing-actions/{id}/`, `management/accounts/{id}/` |
| Duplicates queue | `management/property-duplicates/`, `.../confirm/`, `.../dismiss/` |
| Street and village approval | `POST localities/{id}/approve/` |
| Message templates in both languages | `management/notifications/message-templates/` |
| Location check revoke | `POST management/verifications/documents/{id}/revoke/` |

---

## Phase 6: Smaller public and lister screens

| Item | Requirement | Endpoints |
|---|---|---|
| Public lister profile | IDV-06 | `GET listers/{id}/` |
| Lead notes and customer list | LEAD-02, LEAD-06 | `POST leads/{id}/notes/`, `GET leads/customers/` |
| Buyer's own enquiries | SRD 24 | To confirm: the leads list is lister-scoped |
| Notifications marked read | NTF-01 | `POST notifications/{id}/read/` |
| Marketing consent page | MAR-03 | `marketing/consent/`; campaign emails should link to a frontend page, not the API |

---

## Phase 7: Backend gaps

| Item | Requirement | Note |
|---|---|---|
| Bulk import from Excel or CSV with batch photos and a validation report | LST-11 (Must) | Not in the backend. Needs models, parsing, matching photos by row reference, duplicate checks and a confirm step, then the screens |
| `/auth/me/` returns roles, permissions and account category | ACC, NFR-03 | Lets the frontend drop the `loadAccess()` probes |
| Face matching to assist identity review | IDV-05 (Should) | After launch unless promoted |
| Automatic tax receipts through a VFD provider | PAY-14 (Should) | After TRA registration |
| Historical imagery | MAP-07 (Should) | Depends on the map provider |

---

## Phase 8: Launch readiness

1. **Non-functional checks:** search under 2 s, property page under 3 s, market panel under 5 s on a throttled 3G profile; uploads that survive a dropped connection; forms that keep unsent entries; WCAG 2.1 AA pass on the main flows (NFR-01, NFR-02, NFR-10).
2. **Full acceptance run** of every SRD Given, When, Then table on PostgreSQL/PostGIS.
3. **Production configuration:** `production_preflight`, HTTPS, S3 bucket with public access blocked, backups and restore test, monitoring (NFR-06 to NFR-08). See [M26_PRODUCTION_RUNBOOK.md](M26_PRODUCTION_RUNBOOK.md).
4. **Oweru's external services (SRD 2.6):** the dedicated WhatsApp number linked to WhatsApp Web on staff computers, the map and satellite provider contract and key, TRA registration for EFD or VFD receipts.
5. **Director decisions (SRD 26):** rate table bands, full check fee, Property ID format, licence for receiving buyer money, legal review of wording.
6. **User acceptance** with real staff on each desk, then go-live.
