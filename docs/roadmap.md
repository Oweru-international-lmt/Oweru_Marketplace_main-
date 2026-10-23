# Roadmap: the remaining phases

What is left to build for the Phase 1 launch, in order, with the user flow, screens, endpoints and finish line of each phase. Requirements are in [srd.md](srd.md); what already exists is in [architecture.md section 10](architecture.md#10-status-by-module).

Last updated: 23 October 2026.

| Phase | Area | Status |
|---|---|---|
| 1 | Deals and money | Done (21 October 2026); the rate table editor and Oweru's bank account form were finished in Phase 5 |
| 2 | Partner work: site capture and verification tasks | Done (22 October 2026) |
| 3 | Partner management: local officials and professionals | Done (22 October 2026). Officials now register through a one-time link (new backend) |
| 4 | Rest of the full check | Done (22 October 2026), with decision D3 (tax receipt optional) |
| 5 | Management administration | Done (23 October 2026), with the D5 examples (`manage.py seed_example_values`) |
| 6 | Smaller public and lister screens | Done (23 October 2026) |
| 7 | Backend gaps | D2 and D4 done; `/auth/me/` roles, face matching, VFD receipts and historical imagery remain |
| 8 | Launch readiness | **Next** |

Why this order: a sale cannot reach Won without Phase 1, and a full check cannot finish without Phases 2 to 4. Management administration (Phase 5) is needed before launch but nothing else depends on it.

## Project decisions (22 October 2026)

Decisions by the product owner that change the SRD and PRD. They apply everywhere in the code and docs; where the SRD says otherwise, these win.

| ID | Decision | What it means for the build |
|---|---|---|
| D1 | **No bulk upload.** LST-11 (Excel or CSV import with batch photos) is out of scope. | Listings are added one at a time. Remove bulk import from plans, screens and launch checks. |
| D2 | **No paid map provider. Use free imagery that is good and accurate enough for plots.** | See [Maps and imagery](#maps-and-imagery) below. |
| D3 | **Tax receipts through TRA are left out for now.** No TRA registration, no EFD or VFD integration (PAY-14). | Recording a tax receipt (PAY-11) stays available but optional: it does not block completing a sale and is not listed as waiting work. |
| D4 | **Property ID format: `OWR-<region postcode>-<number>`**, for example `OWR-11-04217` for a property in Dar es Salaam. | See [Property ID](#property-id) below. |
| D5 | **Commission rates and the full check fee start as example tables that the responsible people can change.** | Management edits the commission rate table; the Director sets the full check fee. Both screens are in Phase 5, seeded with the examples below. |

### Maps and imagery

Research (22 October 2026) of free sources that may legally be used in a commercial website:

| Source | Detail and accuracy | Free allowance | Commercial use | Use in Oweru |
|---|---|---|---|---|
| Esri World Imagery through an ArcGIS Location Platform account | About 0.3 to 0.5 m in towns (commercial satellite and aerial), coarser in some rural areas | 2,000,000 basemap tiles a month, then USD 0.15 per 1,000 | Yes, it is Esri's pay-as-you-go platform for apps; needs a free account and an API key, and "Powered by Esri" attribution | **Main satellite layer** for staff location checks, full check review and boundary capture |
| Mapbox Satellite | Similar city detail | 750,000 raster tile requests a month | Yes, pay-as-you-go | Backup if the Esri allowance is ever exceeded |
| Google Map Tiles API (satellite) | Very good | 100,000 tiles a month, billing account required | Yes | Not used: smallest allowance and needs a card |
| OpenAerialMap drone imagery (Dar es Salaam Ramani Huria, Zanzibar Mapping Initiative) | About 5 to 10 cm, but only some areas and years | Free | Openly licensed (check each image's licence, usually CC BY 4.0) | Optional extra layer where it exists |
| EOX Sentinel-2 cloudless | 10 m, too coarse for plots | Free | Only the 2016 layer allows commercial use | Not used for checks |
| MapTiler free plan | Good | Small | **No, non-commercial only** | Not used |
| OpenStreetMap | Streets and place names | Free data (ODbL); the public tile server forbids heavy use | Yes for the data | Street view through Esri's free street basemap, not the public OSM server |

Decision: Esri World Imagery and Esri streets with a free ArcGIS Location Platform key, stored as a setting (`VITE_ESRI_API_KEY`). 2,000,000 tiles a month is far more than Oweru's staff and site capture will use in Phase 1 (one map review is roughly 50 to 200 tiles). Never claim imagery proves ownership (MAP-09), and always show the attribution.

### Property ID

- Tanzania has no common format for listing references on property websites. Officially, land is identified by its certificate of title number (CT No.), its plot and block number with the locality, and Land Office (L.O.) numbers. Those stay as separate fields on the Property Record; Oweru's own ID does not replace them.
- Every ward has an official five-digit postcode (TCRA, Government Notice 240 of 2016), and the first two digits name the region: 11 Dar es Salaam, 23 Arusha, 41 Dodoma, and so on.
- Format: `OWR-` + two-digit region postcode + `-` + a five-digit running number per region (six digits once a region passes 99,999). Example `OWR-11-04217`. Digits only after the prefix, so it is easy to read out on the phone, type on any keyboard and recognise by region. The current random IDs (`OWR-` + hex) move to this format for new records; existing records keep theirs.

### Example values (editable)

Commission rate table (total commission 10 percent of the owner's price, split by selling price; management edits it, PAY-01). The market reports agency fees of about 3 to 5 percent and informal dalali fees up to about 10 percent, so these are starting points only:

| Selling price (TSh) | Oweru share | Agent share | Total |
|---|---|---|---|
| Up to 50,000,000 | 4% | 6% | 10% |
| 50,000,001 to 200,000,000 | 3% | 7% | 10% |
| 200,000,001 to 500,000,000 | 2.5% | 7.5% | 10% |
| Above 500,000,000 | 2% | 8% | 10% |

Full check fee (set by the Director). Example: **TSh 450,000**, built from:

| Part | Example (TSh) | Basis |
|---|---|---|
| Land Registry official search | 40,000 | Fee on the Ministry of Lands search form |
| Local office confirmation | 30,000 | Letter and stamp from the street or village office |
| Boundary and site capture review | 130,000 | Government benchmark for surveying one plot (2021 regularization guideline) |
| Land-use or planning check where needed | 100,000 | Professional's time |
| Oweru verifier review and written report | 150,000 | Staff time, cheaper than a lawyer's TSh 300,000 to 1,500,000 checks |
| **Total** | **450,000** | |

Sources: [Esri pricing](https://location.arcgis.com/pricing/), [Esri Leaflet imagery tutorial](https://developers.arcgis.com/esri-leaflet/maps/raster-tile-basemaps/display-multiple-basemap-layers/), [Mapbox pricing](https://www.mapbox.com/pricing), [Google Maps pricing list](https://developers.google.com/maps/billing-and-pricing/pricing), [MapTiler terms](https://www.maptiler.com/terms/engine/), [EOX Sentinel-2 cloudless 2024](https://eox.at/2025/03/sentinel-2-cloudless-2024/), [Ramani Huria](https://en.wikipedia.org/wiki/Ramani_Huria), [TCRA postcode list](https://tcra.go.tz/services/publication-of-postcode-list), [Land Registry search form](https://www.lands.go.tz/uploads/documents/sw-1693126594-1463151589-Search%20Request.doc), [survey fee cut](https://www.tanzaniainvest.com/construction/land-survey-fee-cut), [agent fees](https://theafricanvestor.com/blogs/news/tanzania-property-taxes-fees), [Coldwell Banker Tanzania](https://coldwellbanker.tz/investing-guides/smart-buyer-tips-tanzania/), [legal check costs](https://globallawexperts.com/real-estate-lawyer-tanzania/).

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
9. Management may record the official tax receipt number and copy (optional while TRA is deferred, decision D3).
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

### Step 2: references board

Published 21 October 2026 as "Oweru Deals Inspiration": 24 references (D1 to D24) from Dribbble and Pinterest in four groups: buyer payment (D1 to D5), the deal page (D6 to D11), agent money (D12 to D17), management desks (D18 to D24). Recommended picks: D1, D2, D3, D6, D7, D8, D12, D13, D14, D16, D18, D19, D20, D21.

### Steps 3 to 6: what was built

Picks: D1, D2, D3, D6, D7, D8, D12, D13, D14, D16, D18, D19, D20, D21.

- **Buyer:** `/purchases` and `/purchases/:dealId`. D3's steps over a receipt card, each transfer as a D1 bank card with copy buttons, and D2's slip upload, pending review and upload-another states.
- **Lister:** `/lister/deals` and `/lister/deals/:dealId` (D8 receipt column, D6 numbered progress on wide screens, D7 tick timeline on phones, actions to share the payment page, get the owner's receipt confirmed, and upload and confirm the agreement); `/lister/payouts` (D12 on wide screens, D13 on phones); `/lister/bank` (D14 with a live card preview); the D16 payout preview inside the listing form.
- **Management:** `/staff/deals` (D18), `/staff/deals/:dealId` (D20 with the D19 transfer panel: confirm Oweru's money, approve the agreement, record the tax receipt, complete the sale), `/staff/payouts` (D21 with hold, release and record payment in a side panel).
- **Backend:** deal reads now carry the property summary, step times, documents, tax receipt and payout, shaped by role; the payout list names the agent and their bank only for management; message links for new leads, deals, payouts, identity decisions, free check reports and the lister's payment-page share now open frontend pages.
- **Motion:** amounts count up, D3's lines draw in and its ticks pop in turn, the D6 current step pulses, timelines stagger in, copy buttons turn into ticks, transfer cards rise on scroll, the D19 panel slides in, the payouts card shimmers, filter pills slide, and the bank card fills in as the lister types. Everything respects reduced motion.
- **Verified** in the preview with four seeded deals: a buyer uploaded a slip, then management confirmed Oweru's money, approved the agreement, recorded the tax receipt, completed the sale and paid the agent, all through the screens.
- **Not built (no pick):** the rate table editor and Oweru's receiving bank account form. Both are management settings and move to Phase 5.

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
| Settings with change history (including both full check scope languages and the full check fee, which only the Director can change; seeded with the example in decision D5) | `management/settings/`, `management/verification-settings/{key}/` |
| Audit log | `GET management/audit/` |
| Suspend and restore listings and accounts with a reason | `management/listings/{id}/suspend/`, `.../restore/`, `management/listing-actions/{id}/`, `management/accounts/{id}/` |
| Duplicates queue | `management/property-duplicates/`, `.../confirm/`, `.../dismiss/` |
| Street and village approval | `POST localities/{id}/approve/` |
| Message templates in both languages | `management/notifications/message-templates/` |
| Location check revoke | `POST management/verifications/documents/{id}/revoke/` |
| Commission rate tables: draft bands, publish (moved from Phase 1) | `GET`/`POST commissions/rate-tables/`, `PUT .../{id}/`, `POST .../{id}/publish/` |
| Oweru's receiving bank account (moved from Phase 1) | `PUT management/finance/oweru-bank/` |

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
| `/auth/me/` returns roles, permissions and account category | ACC, NFR-03 | Lets the frontend drop the `loadAccess()` probes |
| Face matching to assist identity review | IDV-05 (Should) | After launch unless promoted |
| Automatic tax receipts through a VFD provider | PAY-14 (Should) | Deferred with TRA (decision D3) |
| Historical imagery | MAP-07 (Should) | Not in the free Esri layer; Esri's World Imagery Wayback is a possible free source to check later |
| New Property ID format | Decision D4 | Done: new records get `OWR-<TCRA region postcode>-<number>` (Zanzibar and unknown regions use 00); existing IDs kept |
| Free satellite key | Decision D2 | Done in the frontend: maps use `VITE_ESRI_API_KEY` when set, with Esri attribution |

---

## Phase 8: Launch readiness

1. **Non-functional checks:** search under 2 s, property page under 3 s, market panel under 5 s on a throttled 3G profile; uploads that survive a dropped connection; forms that keep unsent entries; WCAG 2.1 AA pass on the main flows (NFR-01, NFR-02, NFR-10).
2. **Full acceptance run** of every SRD Given, When, Then table on PostgreSQL/PostGIS.
3. **Production configuration:** `production_preflight`, HTTPS, S3 bucket with public access blocked, backups and restore test, monitoring (NFR-06 to NFR-08). See [M26_PRODUCTION_RUNBOOK.md](M26_PRODUCTION_RUNBOOK.md).
4. **Oweru's external services (SRD 2.6):** the dedicated WhatsApp number linked to WhatsApp Web on staff computers, and a free ArcGIS Location Platform account for the satellite key (decision D2). TRA registration is deferred (decision D3).
5. **Director decisions (SRD 26):** confirm or edit the example rate table and full check fee in their settings screens (decision D5); the Property ID format is decided (D4). Still open: the licence for receiving buyer money and legal review of wording.
6. **User acceptance** with real staff on each desk, then go-live.
