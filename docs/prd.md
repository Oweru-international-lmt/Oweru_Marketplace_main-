# Oweru Marketplace: Product Requirements Document (PRD)

Phase 1 (web). The business view of what Oweru Marketplace is for, who uses it and how it should behave.

| | |
|---|---|
| Source | `Oweru-Marketplace-PRD-v1.8.docx` (Oweru International Ltd), converted to Markdown for the repository. The wording below is the source text; only the formatting changed. |
| Version | 1.8, 29 September 2026, draft for Director approval |
| Read with | [srd.md](srd.md) (what to build, with requirement IDs and acceptance tests) |
| Precedence | The SRD v1.3 is the build specification. Where the two differ, follow the SRD. |

## Project decisions that change this document (22 October 2026)

The product owner decided the following; they win over the text below. Details and research are in [roadmap.md, Project decisions](roadmap.md#project-decisions-22-october-2026).

| ID | Decision | Affects |
|---|---|---|
| D1 | No bulk upload of listings | FR-12, journey 4.1 step 3 |
| D2 | No paid map provider: free Esri World Imagery through a free ArcGIS key, plus open drone imagery where it exists | Section 10 (satellite imagery), section 13 |
| D3 | Tax receipts through TRA left out for now; recording a receipt is optional | FR-24, section 10 (tax receipts), section 13 |
| D4 | Property ID format `OWR-<region postcode>-<number>`, e.g. `OWR-11-04217` | Section 13 (Property ID format) |
| D5 | Commission rate table and full check fee start as editable example tables | Sections 5.4, 11 and 13 |

## Where the SRD v1.3 overrides this PRD

| PRD says | SRD v1.3 says (follow this) |
|---|---|
| FR-03: sign in with phone number and password; reset by email or WhatsApp | ACC-02, ACC-03, ACC-05: sign in with **email** and password. Every account has an email address. Email and phone are each unique. Reset by an emailed one-time link, or a reset link sent from the WhatsApp outbox after staff check who the person is. |
| Requirement IDs FR-01 to FR-85 | The SRD renumbers them by module (ACC, IDV, LST, SRC, LEAD, PAY, LVL, VER, FUL, MAP, LOC, PRO, FRC, CMP, MON, MAR, NTF, ADM, NFR). Use the SRD IDs in tickets, commits and tests. |

The *System Overview and Gap Resolutions v2* (September 2026) came before this PRD. It still describes SMS codes, mobile money and professionals without logins; all three were dropped. Use it only for background on why decisions were made.

---

| **Item** | **Detail** |
|----|----|
| Organisation | Oweru International Ltd |
| Product | Oweru Marketplace |
| Version | 1.8 |
| Date | 29 September 2026 |
| Status | Draft for Director approval |
| Audience | Director, Head of Operations, product owner, Marketplace build team |
| Phase | Phase 1: web system |

## Contents

- [1. Product summary](#1-product-summary)
  - [1.1 Problem](#11-problem)
  - [1.2 Goals](#12-goals)
  - [1.3 Out of scope for Phase 1](#13-out-of-scope-for-phase-1)
- [2. Users and roles](#2-users-and-roles)
  - [2.1 Public users](#21-public-users)
  - [2.2 Verification partners](#22-verification-partners)
  - [2.3 Oweru team](#23-oweru-team)
  - [2.4 How WhatsApp is used in Phase 1](#24-how-whatsapp-is-used-in-phase-1)
  - [2.5 Who can do what](#25-who-can-do-what)
- [3. Verification ladder](#3-verification-ladder)
  - [3.1 Rules that must never break](#31-rules-that-must-never-break)
- [4. Key user journeys](#4-key-user-journeys)
  - [4.1 Listing a property](#41-listing-a-property)
  - [4.2 From enquiry to closed deal](#42-from-enquiry-to-closed-deal)
  - [4.3 Paid full check (Level 3)](#43-paid-full-check-level-3)
  - [4.4 Free public check](#44-free-public-check)
  - [4.5 Local office check (Serikali za Mitaa)](#45-local-office-check-serikali-za-mitaa)
  - [4.6 Professional jobs](#46-professional-jobs)
- [5. Payments and commission](#5-payments-and-commission)
  - [5.1 Two prices on every agent listing](#51-two-prices-on-every-agent-listing)
  - [5.2 How the money moves on an agent listing](#52-how-the-money-moves-on-an-agent-listing)
  - [5.3 Worked example](#53-worked-example)
  - [5.4 Commission rate table](#54-commission-rate-table)
  - [5.5 Owner listings with no agent](#55-owner-listings-with-no-agent)
  - [5.6 Payment steps at closing](#56-payment-steps-at-closing)
  - [5.7 Protecting the commission](#57-protecting-the-commission)
- [6. Market monitoring panel](#6-market-monitoring-panel)
- [7. Complaints](#7-complaints)
  - [7.1 Channels for lodging a complaint](#71-channels-for-lodging-a-complaint)
  - [7.2 Complaint types and who handles them](#72-complaint-types-and-who-handles-them)
  - [7.3 How a complaint is handled](#73-how-a-complaint-is-handled)
- [8. Functional requirements](#8-functional-requirements)
  - [8.1 Accounts, roles and identity](#81-accounts-roles-and-identity)
  - [8.2 Property records and listings](#82-property-records-and-listings)
  - [8.3 Leads and deals](#83-leads-and-deals)
  - [8.4 Payments and commission](#84-payments-and-commission)
  - [8.5 Buyer discovery](#85-buyer-discovery)
  - [8.6 Verification display](#86-verification-display)
  - [8.7 Verification jobs](#87-verification-jobs)
  - [8.8 Listing checks](#88-listing-checks)
  - [8.9 Full check](#89-full-check)
  - [8.10 Site capture and maps](#810-site-capture-and-maps)
  - [8.11 Free public check](#811-free-public-check)
  - [8.12 Local officials (Serikali za Mitaa)](#812-local-officials-serikali-za-mitaa)
  - [8.13 Professionals](#813-professionals)
  - [8.14 Market monitoring panel](#814-market-monitoring-panel)
  - [8.15 Marketing tools](#815-marketing-tools)
  - [8.16 Complaints](#816-complaints)
  - [8.17 Operations and compliance](#817-operations-and-compliance)
- [9. Non-functional requirements](#9-non-functional-requirements)
- [10. Integrations](#10-integrations)
- [11. Settings and default values](#11-settings-and-default-values)
- [12. Success measures](#12-success-measures)
- [13. Assumptions and open decisions](#13-assumptions-and-open-decisions)
  - [Assumptions](#assumptions)
  - [Open decisions](#open-decisions)

# 1. Product summary

Oweru Marketplace is a Tanzanian web system where buyers find land, houses and commercial property. Properties are listed either by owners themselves or by independent agents selling on an owner's behalf. Its advantage is honesty: every property shows exactly what Oweru has checked and what it has not. Buyers can pay for a full ownership check when a deal is about to close. Anyone can run a free location check on any property, including properties advertised elsewhere, and download the result.

Phase 1 is delivered as a web system only. It works in any modern browser on a phone, tablet or computer, including site capture, which uses the phone browser's location and camera. Messages to users go by ordinary WhatsApp used in the browser, email and on-screen notifications. Text messages (SMS) are not used, to keep costs down. All payments are made by bank transfer between bank accounts.

For owners and agents, the Marketplace is a business tool: listing management, bulk import, a lead pipeline, customer records, deal records and a verified identity. When a deal closes, the buyer pays Oweru's share through the platform. Oweru keeps its commission and pays the agent.

Verification is carried out by a network registered by Oweru: local government officials (Serikali za Mitaa) for each street or village, and professionals (Afisa Mipango Miji, planners and surveyors). Each has a login and a dashboard where they receive verification jobs. For Oweru's team, a market monitoring panel shows what is selling, where and at what price.

## 1.1 Problem

- A competitor already holds a large national database of agents and listings. Agents have no reason to start again elsewhere.

- Buyers cannot tell which listings are genuine. Land fraud and double sales are common.

- Oweru cannot inspect every plot in Tanzania with its own staff, and owners will not hand over title documents just to be listed.

- Oweru starts with no data: no listings, no agents, no boundary data and no contacts in local offices.

## 1.2 Goals

1.  Give owners and agents a reason to list on Oweru alongside their existing channels.

2.  Show every buyer, honestly, what has and has not been checked on each property.

3.  Sell a paid full ownership check at the moment it matters, when a deal is closing.

4.  Build a growing national network of registered local officials and professionals who carry out verification jobs.

5.  Use the free public check and its downloadable report to bring serious buyers to Oweru.

6.  Collect Oweru's commission reliably at the moment each deal closes, and pay agents quickly.

7.  Give Oweru's team clear market data to guide improvement and growth.

## 1.3 Out of scope for Phase 1

- Native mobile apps for Android or iOS. Phase 1 is web only.

- Text messages (SMS). WhatsApp and email are used instead.

- Automatic WhatsApp messaging through Meta's paid business platform.

- Refunds. Planned for the next phase.

- Referral tracking and referral rewards. Planned for version 2.

- Rental properties.

- Company or agency accounts. Every agent registers as an individual.

- Self-registration by local officials or professionals. Oweru invites and registers them.

- Copying listings from competitor websites.

# 2. Users and roles

## 2.1 Public users

| **Role** | **Who** | **Main actions** |
|----|----|----|
| Buyer | Member of the public buying property | Search, enquire, request viewings, run the free check, pay for a full check, pay for a property at closing |
| Owner | Legal owner of a property. Can sell directly with an account, or let an agent sell it | Selling directly: list and manage properties, handle leads and viewings, close deals. Through an agent: no account needed, confirms their price, bank account, consent and payment received by WhatsApp confirmation |
| Agent | Independent broker (dalali) selling on behalf of an owner. Not Oweru staff | Enter the owner's price and the selling price, list and import properties, manage leads and customers, capture site evidence, introduce buyer and owner at closing, receive payout from Oweru |

## 2.2 Verification partners

Partners are registered by Oweru only. Each has a login and a dashboard where they receive and complete verification jobs.

| **Partner** | **Who** | **Jobs they receive** |
|----|----|----|
| Local official (Serikali za Mitaa) | Mwenyekiti or Mtendaji of a street (Mtaa) or village | Local office checks for properties in their own street or village: confirming the owner, any other sale, any dispute and agreed boundaries |
| Afisa Mipango Miji | Town planning officer | Land-use checks from official planning records: permitted use, approved town plans, planned roads and public reserves affecting the plot |
| Planner | Registered land-use planner | Planning reviews: plot layout, development restrictions and the planning context of the area |
| Surveyor | Registered land surveyor | Boundary jobs: locating beacons, capturing corner points, measuring area and checking overlap on site |

## 2.3 Oweru team

| **Role** | **Main duties in the system** |
|----|----|
| Director | Full control of the system. Same permissions as the Head of Operations |
| Head of Operations | Approves identities, registers and approves local officials and professionals, assigns verification jobs, manages the commission rate table, settings and the office list, confirms payments received and releases agent payouts, settles complaints and conflicts, manages staff accounts, views the market monitoring panel |
| Verifier | Reviews evidence and partner submissions, assigns jobs to partners, confirms ownership with the Land Registry, records results |
| Marketer | Manages featured listings and homepage banners, content pages and email marketing campaigns to users who agreed to receive them, views the market monitoring panel and lead source reports. Cannot see owners' private details, identity documents or payment details |

*In this document, "management" means the Director and the Head of Operations. "Lister" means whoever listed the property: the owner or the agent. "Partner" means a registered local official or professional. One public account can both buy and list. When listing, the user states whether they are the owner or an agent.*

## 2.4 How WhatsApp is used in Phase 1

Phase 1 uses ordinary WhatsApp opened in the browser (WhatsApp Web) on Oweru's own number, not Meta's paid business platform. The system never sends WhatsApp messages by itself. It prepares each message, and a person sends it with one click:

- **Staff outbox.** Messages to owners, local offices, professionals and complainants wait in a WhatsApp outbox screen. A staff member clicks Send, WhatsApp opens with the message already written, and they press send.

- **Self-service.** Where the user is on the website, a button opens their own WhatsApp with the message ready, for example to contact a lister or send a free check report to themselves.

Everything important is also shown on screen and sent by email where the person has an email address. No automation tools may be used with Oweru's WhatsApp number, because WhatsApp bans numbers used that way.

WhatsApp confirmation: Oweru staff send the person a short link from the outbox. They open it, see what they are agreeing to, for example the price and commission, and tap Confirm. Wherever this document says someone "confirms by WhatsApp" or is "alerted by WhatsApp", it means a message sent this way.

## 2.5 Who can do what

| **Function** | **Buyer** | **Owner** | **Agent** | **Local official** | **Professional** | **Verifier** | **Marketer** | **Management** |
|----|----|----|----|----|----|----|----|----|
| Search and enquire | Yes | Yes | Yes |  |  |  |  | Yes |
| List and manage properties |  | Yes | Yes |  |  |  |  | Yes |
| See the owner's price |  | Own only | Own listings |  |  |  |  | Yes |
| Receive and complete verification jobs |  |  |  | Own street | Assigned | Yes |  |  |
| Record verification results |  |  |  |  |  | Yes |  | Yes |
| Register partners |  |  |  |  |  |  |  | Yes |
| Commission rate table |  | View | View |  |  |  |  | Edit |
| Confirm payments and release payouts |  |  |  |  |  |  |  | Yes |
| Lodge a complaint | Yes | Yes | Yes | Yes | Yes |  |  |  |
| Handle complaints |  |  |  |  |  | Verification |  | All |
| Banners, featured listings, campaigns |  |  |  |  |  |  | Yes | Yes |
| Market monitoring panel |  |  |  |  |  |  | Yes | Yes |
| Staff accounts and settings |  |  |  |  |  |  |  | Yes |

# 3. Verification ladder

Every property sits on one level. The level is calculated from completed and current checks and is never set by hand.

| **Level** | **What is checked** | **Label shown to buyer** | **Does not prove** |
|----|----|----|----|
| 0 Listed | Nothing | Listed by \[name\]. Not verified by Oweru | Anything |
| 1 Lister Verified | Identity of the lister: national ID, phone, live selfie | Listed by \[name\], identity verified by Oweru | Anything about the property. An owner's identity does not prove ownership. An agent's identity does not mean they work for Oweru |
| 2 Location Checked | Remote: place exists at the pin, no known duplicate, photos fit the place, no gross location lie | Location and details checked. This is not ownership verification | Ownership, boundaries, title |
| 3 Oweru Verified | Ownership confirmed at source, local office check, boundary captured and reviewed, no competing claims, owner consent | Oweru Verified, with date and expiry | Top level |

## 3.1 Rules that must never break

- **The wall.** Only Level 3 may use the Oweru Verified name, badge style or promise.

- **Owner is a claim until Level 3.** A property listed by its owner shows "Listed by \[name\], who states they are the owner" until ownership is confirmed.

- **Location is not ownership.** Level 2 and the free check always state they are not ownership verification.

- **Verdict, not method.** The free check returns verdicts only. Coordinates, boundaries and methods are never exposed.

- **Disclose first.** Fees, commission and the limits of each level are shown before anyone pays or relies on a result.

- **Honest coverage.** Checks based on Oweru records say so, for example "No match among properties Oweru has on record".

- **Owner privacy on agent listings.** The owner's name, contact and price are never shown to buyers. Oweru uses them only for consent, payment and verification, and never markets to the owner.

- **No conflict of interest.** A partner never receives a job on a property they own, list or are related to.

- **True price on the sale agreement.** The signed sale agreement always states the exact final selling price the buyer pays.

- **No guarantee wording** until the guarantee is legally defined. Until then, Level 3 reads "Oweru Verified: full check completed".

# 4. Key user journeys

## 4.1 Listing a property

1.  User signs up with a phone number and password. A lister confirms their number by opening a link Oweru sends them on WhatsApp.

2.  User chooses "I am the owner" or "I am an agent" and verifies identity with national ID and a live selfie.

3.  User adds properties one by one or imports them from Excel or CSV, including the full locality: region, district, ward, and street (Mtaa) or village.

4.  An agent enters the owner's name and WhatsApp number, the owner's price and the selling price. The system shows the agent the payout breakdown from the commission rate table.

5.  Every lister adds a bank account for receiving money: the agent for payouts, the owner for the buyer's payment.

6.  On an agent listing, the owner confirms their price, the 10 percent commission and their bank account by WhatsApp.

7.  Listings go live at Level 0 showing the selling price. Duplicates, including the same property listed by its owner and an agent, are linked and flagged for review.

8.  Oweru staff run the remote location check and raise eligible listings to Level 2.

## 4.2 From enquiry to closed deal

1.  Buyer searches by area, category, price, size and verification level, on a list or map.

2.  Buyer sends an enquiry or viewing request. This creates a lead for the lister.

3.  Lister moves the lead through Contacted, Viewing and Negotiation.

4.  At Closing, the lister enters the final selling price and the buyer is offered the full check. On an agent listing, the agent introduces the buyer to the owner.

5.  The buyer pays by bank transfer as set out in section 5, and the lister uploads the signed sale agreement showing the exact final selling price.

6.  Once the owner confirms receipt and management confirms Oweru's receipt, the lead is marked Won and Oweru pays the agent.

## 4.3 Paid full check (Level 3)

1.  Buyer sees the fee and what the check covers, then pays by bank transfer.

2.  Owner consents: in their account if they listed the property, or by WhatsApp confirmation if an agent listed it.

3.  Owner or agent enters the ownership document details and captures the boundary on site through the Oweru website on a phone.

4.  The system sends the local office check to the registered official for the property's street or village. See section 4.5.

5.  Where needed, the verifier assigns a surveyor for the boundary, and an Afisa Mipango Miji or a planner for land use. See section 4.6.

6.  Verifier reviews all submissions against satellite imagery, the survey plan, the stated area and other boundaries on record, and confirms ownership with the Land Registry where the land is titled.

7.  Buyer receives a written report. A "do not buy" result is delivered as a success. The property reaches Level 3 only if all checks pass.

## 4.4 Free public check

1.  Anyone enters a map pin, the stated description and optional photos. A link to an outside listing may be saved as a reference.

2.  User enters their WhatsApp number. This registers them as a lead.

3.  System shows the verdict on screen: location exists, duplicates on record, photo mismatch, or gross location mismatch.

4.  User downloads the report as a PDF, and can tap "Send to my WhatsApp" to keep the link in their own WhatsApp.

5.  The verdict and the report both state that this is not ownership verification and offer the paid full check.

6.  Submission is saved as an outside Property Record. Limit: 5 checks per WhatsApp number per day.

The report contains a reference number, the date, the property details as entered, each verdict in plain words, the statement that it is not ownership verification, and how to order the full check. It never contains coordinates, boundaries or the method used.

## 4.5 Local office check (Serikali za Mitaa)

Part of the full check. Used when the property has no registered title, and to confirm there is no dispute on titled land. Every property records its full locality: region, district, ward, and street (Mtaa) or village. The system uses this to find the right office directly.

**When an official is already registered for the street or village:**

1.  The system matches the property's locality to the registered official and places the job in their dashboard, with a WhatsApp alert.

2.  The official opens the job, answers the five questions and uploads a signed and stamped confirmation and any supporting documents.

3.  The verifier reviews the submission, phones the official only if something does not match, and records the result: Confirmed, Not confirmed, or Problem found.

**When no official is registered yet:**

1.  Oweru staff obtain the office's WhatsApp number through the ward or council office. A number given by the owner or agent is never used.

2.  The system sends a registration link to that number by WhatsApp.

3.  The official registers: full name, position (Mwenyekiti or Mtendaji), national ID number, live photo, office locality (street or village, ward, district, region) and a photo of the office stamp.

4.  The Head of Operations approves the registration after confirming the official with the ward or council office. The official then has a login and a dashboard.

5.  The waiting job appears in the official's dashboard and the check continues as above.

Once registered, the official receives every future job for properties in the same street or village. Over time Oweru builds a national network of officials, and management can see on a map which streets, villages and wards are covered.

**The five questions:**

1.  Is this plot in your Mtaa or village?

2.  Do you know \[owner name\] as the owner of this plot?

3.  Has this plot been sold or given to anyone else?

4.  Is there any dispute over this plot?

5.  Are the boundaries agreed with the neighbours?

**Rules:**

- Every answer is tied to the named, registered official who gave it, so they are accountable for it.

- An official who leaves office is deactivated, and their replacement is invited to register.

- If a job is not completed within 14 days, it is marked Not completed and the buyer is told.

The buyer sees, for example: "Confirmed by the Mtaa office of \[name\] on \[date\]." If the land has no registered title, the page adds: "No registered title. Local office records give less protection than a title."

## 4.6 Professional jobs

1.  Oweru registers each professional and gives them a login. They cannot sign up themselves.

2.  The verifier assigns a job to a professional of the right type who covers the property's area: a surveyor for boundaries and area, an Afisa Mipango Miji for official land-use records, a planner for planning review.

3.  The professional receives a WhatsApp alert, sees the job in their dashboard, and accepts or declines it.

4.  The professional completes the job and uploads their findings, report and evidence, such as corner points, beacon photos or planning extracts.

5.  The verifier reviews the submission. The result is tied to the professional's name and registration number.

# 5. Payments and commission

## 5.1 Two prices on every agent listing

| **Price** | **Who enters it** | **Who sees it** |
|----|----|----|
| Owner's price: what the owner wants for the property | Agent, confirmed by the owner by WhatsApp | Owner, agent and management. Never buyers |
| Selling price: what the buyer is asked to pay | Agent | Everyone. Shown on the property page |

The selling price can never be lower than the owner's price unless the owner confirms a new, lower owner's price.

## 5.2 How the money moves on an agent listing

- The owner receives 90 percent of the owner's price, paid by the buyer directly into the owner's bank account.

- The remaining 10 percent of the owner's price is the commission. It is split between Oweru and the agent according to the commission rate table.

- The buyer pays Oweru the 10 percent commission plus the difference between the selling price and the owner's price.

- Oweru keeps its share and pays the agent the agent's share plus the whole difference.

## 5.3 Worked example

Selling price TSh 120,000,000. Owner's price TSh 100,000,000. Commission band: Oweru 3 percent, agent 7 percent.

| **Step** | **Amount (TSh)** |
|----|----|
| Buyer pays the owner directly: 90 percent of the owner's price | 90,000,000 |
| Buyer pays Oweru: 20,000,000 difference plus 10,000,000 commission | 30,000,000 |
| Buyer pays in total (the selling price) | 120,000,000 |
| Oweru keeps: 3 percent of the owner's price | 3,000,000 |
| Oweru pays the agent: 7 percent of the owner's price plus the 20,000,000 difference | 27,000,000 |
| Owner receives | 90,000,000 |

## 5.4 Commission rate table

Management sets the rate table. Agents see it in their dashboard and while listing, so they know Oweru's share before they list. The total commission is always 10 percent of the owner's price. The table sets how that 10 percent is split, by selling price. The figures below are examples until the Director sets them.

| **Selling price (TSh)**    | **Oweru share** | **Agent share** | **Total** |
|----------------------------|-----------------|-----------------|-----------|
| Up to 50,000,000           | 4%              | 6%              | 10%       |
| 50,000,001 to 200,000,000  | 3%              | 7%              | 10%       |
| 200,000,001 to 500,000,000 | 2.5%            | 7.5%            | 10%       |
| Above 500,000,000          | 2%              | 8%              | 10%       |

All percentages are of the owner's price. The rate that applies is the one in force when the listing was created, so later table changes never surprise an agent mid-deal.

## 5.5 Owner listings with no agent

Proposed: the buyer pays the owner the selling price less Oweru's share, and pays Oweru's share to Oweru. Oweru's share comes from the same rate table. Example: a TSh 100,000,000 owner listing in the 3 percent band. The buyer pays the owner TSh 97,000,000 and pays Oweru TSh 3,000,000.

## 5.6 Payment steps at closing

1.  At Closing, the lister enters the final selling price. The system recalculates the breakdown.

2.  The buyer sees two bank payment instructions: the amount to pay into the owner's bank account, and the amount to pay into Oweru's bank account with a payment reference number.

3.  The buyer pays both by bank transfer and uploads the bank slip or transfer confirmation for each.

4.  The owner confirms receipt of their amount. On an agent listing this is by WhatsApp confirmation.

5.  Management confirms Oweru's bank account has received its amount. The lister uploads the signed sale agreement, which must state the exact final selling price.

6.  The lead is marked Won. Oweru pays the agent into the agent's bank account within 3 working days and issues tax-compliant receipts. The agent sees the payout status in their dashboard.

## 5.7 Protecting the commission

- The agent is paid only through Oweru, so the agent has every reason to make sure the buyer pays through Oweru.

- If a lead is marked Lost and the same property is marked sold to the same buyer within 6 months, management reviews it.

- Disputes about price, payment or commission are lodged as complaints and settled by management, who can hold or adjust a payout with a recorded reason.

# 6. Market monitoring panel

A dashboard for management and the Marketer showing market trends from data inside Oweru. It guides pricing advice, marketing and where to recruit agents and partners.

| **Area** | **What it shows** |
|----|----|
| Supply | Active listings by region, district, ward and category. New listings per week |
| Prices | Average and median selling price, and price per square metre, by area and category, with trends over time |
| Demand | Most searched areas, categories and price ranges. Views and enquiries per listing |
| Hot areas | Map of areas with the most searches, enquiries and deals |
| Speed | Days from listing to first enquiry, and from listing to sale |
| Deals | Deals closed, value, and final selling price compared with the listed selling price |
| Conversion | Enquiry to viewing, viewing to closing, closing to won |
| Trust | Share of listings at each verification level. Free checks run and mismatches found, by area |
| Partner coverage | Streets, villages and wards with a registered local official, and areas covered by each type of professional |
| Listers | New and active agents and owners, listings per lister, response times |
| Marketing | Where visitors and leads came from, and results of each campaign |

Every view can be filtered by date range, region and category, and exported to Excel. Personal details of buyers and owners are never shown in the panel.

# 7. Complaints

Anyone can lodge a complaint: a buyer, an owner, an agent, a partner, or a member of the public reporting a listing. Every complaint goes into one complaints desk inside the system, gets a complaint number, and is tracked until it is closed.

## 7.1 Channels for lodging a complaint

| **Channel** | **How it works** |
|----|----|
| "Lodge a complaint" on the website | Available from every property page, deal page, dashboard and the site footer. No account needed. The form is pre-filled with the property or deal when opened from that page |
| Oweru WhatsApp support number | The person sends a message. Oweru staff log it in the complaints desk, and the person receives the complaint number by WhatsApp |
| Email | Sent to Oweru's complaints email address. Staff log it in the complaints desk the same way |

The complaint form asks for: name, WhatsApp number, whether the person is a buyer, owner, agent, partner or member of the public, the complaint type, the property or deal it concerns if any, a description, and optional evidence such as photos, documents or bank slips.

## 7.2 Complaint types and who handles them

| **Type** | **Examples** | **Handled by** |
|----|----|----|
| Fake or wrong listing | Property does not exist, wrong location, listed without the owner's permission | Head of Operations |
| Conduct | Agent, owner or partner misled someone, asked for money outside Oweru, did not show up | Management |
| Payment or payout | Payment not confirmed, agent payout late or wrong | Management |
| Verification result | Owner or buyer disagrees with a check result | Verifier first, then management |
| Privacy | Personal details misused or shown wrongly | Management |
| Other | Anything else | Head of Operations |

Management settles every conflict between parties. Its decision is recorded with reasons.

## 7.3 How a complaint is handled

1.  The complaint is logged and the person sees the complaint number on screen at once. Complaints lodged by WhatsApp or email get their number the same way within 1 working day.

2.  The system routes it to the right handler by type.

3.  If the complaint concerns a deal whose agent payout has not been made, the payout is held until the complaint is closed.

4.  The handler may ask any party for more information through the complaints desk. The status shows Waiting for information.

5.  The handler records the outcome and the reasons. The person is told the result by WhatsApp.

6.  If the person is not satisfied, they can ask for a final review by the Director within 14 days. The Director's decision is Oweru's final decision.

| **Status** | **Meaning** |
|----|----|
| Received | Logged, complaint number sent |
| In review | The handler is looking into it |
| Waiting for information | The handler has asked someone for more details |
| Resolved | Outcome recorded and the person told |
| Under final review | The Director is reviewing it at the person's request |
| Closed | No further action |

Target times: payment and payout complaints resolved within 5 working days. All others within 10 working days. The person can check the status at any time through a link sent by WhatsApp.

# 8. Functional requirements

*Must means required for launch. Should means wanted and may follow soon after launch.*

## 8.1 Accounts, roles and identity

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| FR-01 | Support public accounts, which can buy and list; partner accounts for local officials and professionals; and staff accounts for Director, Head of Operations, Verifier and Marketer. Each sees only its permitted functions and data. No company accounts. | Must |
| FR-02 | Director and Head of Operations have the same full permissions and can create, change and deactivate staff and partner accounts. | Must |
| FR-03 | Sign in with phone number and password. A lister's phone number is confirmed by a link sent from the WhatsApp outbox. Reset a forgotten password by email, or through Oweru's WhatsApp support number for users without email. | Must |
| FR-04 | Public lister profile with name, photo, areas, property types, verification status, time on Oweru and whether the lister is an owner or an agent. Agent profiles state that the agent is independent of Oweru and acts for the owner. | Must |
| FR-05 | Verify the identity of every lister by national ID number, phone and a live selfie taken with the browser camera and matched to the ID photo. Expires after 12 months. | Must |
| FR-06 | An owner whose property is listed by an agent acts by WhatsApp confirmation without an account. | Must |

## 8.2 Property records and listings

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| FR-07 | One Property Record with a unique Oweru Property ID for every property known to Oweru, including listings, imports, free-check and outside properties. Keeps history and evidence for life. | Must |
| FR-08 | Create and edit listings: category, selling price, pin, region, district, ward, street (Mtaa) or village, size, title type if known, description, features, photos. Region, district, ward and street or village are required. The lister states whether they are the owner or an agent. | Must |
| FR-09 | On agent listings, record the owner's name, WhatsApp number and the owner's price privately, and ask the owner to confirm the owner's price and the 10 percent commission by WhatsApp. | Must |
| FR-10 | Block a selling price below the owner's price unless the owner confirms a new owner's price. | Must |
| FR-11 | Listing statuses: draft, active, under offer, sold, withdrawn, suspended. Only active and under offer are searchable. Only management suspends. Every change is logged. | Must |
| FR-12 | Bulk import from Excel or CSV with an Oweru template and batch photos, including the full locality, with a validation report before publishing. Staff can import on a lister's behalf. | Must |
| FR-13 | Detect duplicates by location, size, description and photo similarity on create, edit and import. Link duplicates, including owner and agent listings of the same property, to one Property Record and flag for review. | Must |

## 8.3 Leads and deals

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| FR-14 | Every enquiry and viewing request creates a lead for the lister. Stages: New, Contacted, Viewing, Negotiation, Closing, Won, Lost, with notes and follow-ups. | Must |
| FR-15 | At Closing, record the final selling price, recalculate the payment breakdown, and offer the buyer the full check. | Must |
| FR-16 | Mark a lead Won only when the owner has confirmed receipt, management has confirmed Oweru's receipt, and the signed sale agreement is uploaded. The lister confirms, and management checks, that the agreement states the exact final selling price recorded in the system. | Must |
| FR-17 | Private customer list per lister with contacts, interests, lead history and notes. | Must |
| FR-18 | Performance figures per listing and overall: views, enquiries, viewings, response time, stage conversion, won deals. | Should |

## 8.4 Payments and commission

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| FR-19 | Commission rate table maintained by management: price bands with Oweru's share and the agent's share, adding up to the configured total of 10 percent of the owner's price. Visible to agents in their dashboard and on the listing form. Each listing keeps the rate in force when it was created. | Must |
| FR-20 | Calculate each deal's breakdown: amount the buyer pays the owner, amount the buyer pays Oweru, Oweru's share, and the agent's payout. On owner listings, calculate the owner amount and Oweru's share from the same table. | Must |
| FR-21 | Record a bank account for each lister: agents for payouts, owners for receiving the buyer's payment. On agent listings the owner confirms their bank account by WhatsApp. Bank details are private and shown only to the buyer at payment time, the account holder and management. | Must |
| FR-22 | Show the buyer bank payment instructions for the owner's account and Oweru's account, with a payment reference number. Accept upload of the bank slip or transfer confirmation for each amount. All payments and payouts are made by bank transfer. | Must |
| FR-23 | Let management confirm payments received, release agent payouts, and hold a payout with a recorded reason. | Must |
| FR-24 | Show each agent their deals, expected payouts, payout status and payment history. Issue tax-compliant receipts for every amount Oweru receives and keeps. | Must |
| FR-25 | Flag for management review any property marked sold to a buyer whose lead on it was marked Lost within the configured period. | Must |

## 8.5 Buyer discovery

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| FR-26 | Search without an account by category, region, district, ward, selling price, size, title type and verification level. List and map views with sorting. | Must |
| FR-27 | Public property page with photos, details, selling price, locality, approximate map position, the lister and the verification panel. On agent listings, the owner's details and the owner's price are never shown. | Must |
| FR-28 | Enquiry, call or WhatsApp contact, and viewing request, each creating a lead and notifying the lister. Full check can be requested from the page. | Must |
| FR-29 | Take payment for full checks by bank transfer, issue receipts, and link each payment to the Property Record and the job. | Must |

## 8.6 Verification display

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| FR-30 | Property page shows each check completed, its date, what was not checked, who carried it out, the reviewing verifier's staff reference, and expiry. | Must |
| FR-31 | Show exactly one level label using fixed approved wording. Reserve the Oweru Verified name and badge style for Level 3. Owner listings below Level 3 say the lister "states they are the owner". Never use the phrase "Oweru Agent". | Must |

## 8.7 Verification jobs

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| FR-32 | Every verification is a job with a named verifier, checklist, evidence, dates, responsibility and result. A job may include tasks for local officials and professionals. | Must |
| FR-33 | Jobs can be started by the owner, or by the agent with owner consent. Buyers are never asked to upload documents they do not hold. | Must |
| FR-34 | Owner consent is given in the owner's account on owner listings, or by WhatsApp confirmation on agent listings. Record who, when and how. Record refusal or no response within 7 days and report it to the buyer. | Must |
| FR-35 | Owners and agents record site evidence. Partners submit answers, findings and documents. Verifiers record checklist results, findings, confirmed documents and notes. Every item records who created it. | Must |
| FR-36 | Full audit trail of what was checked, by whom, when, on what evidence, and the result. | Must |
| FR-37 | Every result has an expiry and can be renewed or re-run. | Must |
| FR-38 | Show the full check fee and what it covers before payment. | Must |
| FR-39 | Adverse results go only to the paying buyer, flag the record internally, block Level 3 and trigger management review. No public fraud label. | Must |
| FR-40 | Never assign a partner a job on a property they own, list or are related to. | Must |

## 8.8 Listing checks

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| FR-41 | Any property can be listed at Level 0 with no checks. No check is a precondition for listing. | Must |
| FR-42 | Remote location check: exists at the pin, no known duplicate, photos consistent, no gross mismatch. Completion gives Level 2. | Must |
| FR-43 | Ownership document confirmed at source by the verifier with the Land Registry or through the local office check, recorded and shown separately. | Must |

## 8.9 Full check

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| FR-44 | Buyer-requested full check: owner identity, authority search, records check, boundary capture, overlap testing, encumbrance enquiry, land-use check, local office check and a written risk assessment. | Must |
| FR-45 | Paid full check on a property found outside Oweru, with evidence kept in its Property Record. | Must |
| FR-46 | Any Oweru assurance holds only while the full check is current at the time of the transaction. | Must |

## 8.10 Site capture and maps

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| FR-47 | The website lets the owner, agent or surveyor capture live corner points on site using the phone browser's location, recording location, time, accuracy and device, and rejecting inaccurate points. Photos and video may come from the camera or the gallery. The system records the source, reads stored location and date, and flags missing or inconsistent data. | Must |
| FR-48 | Level 3 properties have a mapped boundary built from captured corner points, reviewed by a verifier. | Must |
| FR-49 | Store measured area and compare it with the area stated by the owner and in documents. | Must |
| FR-50 | Test overlap with other boundaries on record, roads, reserves and public land in available data. | Must |
| FR-51 | Attach current and historical imagery for occupation and change analysis. | Should |
| FR-52 | Record site risks: flooding, drainage, wetland, steep ground, power lines, road proximity. | Should |
| FR-53 | Record development context: distance to tarmac, water, power, schools, markets. | Should |
| FR-54 | Never imply that maps or imagery prove ownership. | Must |
| FR-55 | Verdicts based on Oweru records state their coverage. | Must |

## 8.11 Free public check

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| FR-56 | Free check anyone can run on any property, returning a plain verdict on screen. | Must |
| FR-57 | Input: pin, stated description, optional photos, optional reference link, and the user's WhatsApp number. Daily limit per number. Save as an outside Property Record and register the user as a lead. | Must |
| FR-58 | Generate a downloadable PDF report with reference number, date, property details as entered, verdicts, the not-ownership statement and how to order the full check. Offer a download button and a "Send to my WhatsApp" button that opens the user's own WhatsApp with the link ready. | Must |
| FR-59 | Verdict and report only. Never expose boundaries, coordinates or method. | Must |
| FR-60 | Offer the paid outside-property check from the verdict and the report. | Must |

## 8.12 Local officials (Serikali za Mitaa)

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| FR-61 | Register of local officials by region, district, ward and street or village, with name, position, national ID number, photo, WhatsApp number, office stamp photo and status: invited, awaiting approval, active or deactivated. | Must |
| FR-62 | Route each local office check automatically to the active official registered for the property's street or village, place it in their dashboard and alert them by WhatsApp. | Must |
| FR-63 | Where no official is registered, let staff enter the office's WhatsApp number obtained through the ward or council, and send a registration link by WhatsApp. Numbers supplied by owners or agents are never used. | Must |
| FR-64 | Registration form: full name, position, national ID number, live photo, office locality and office stamp photo. The Head of Operations approves before the official can log in. Pending jobs then appear in their dashboard. | Must |
| FR-65 | Official's dashboard lists jobs for their street or village. For each job the official answers the five questions and uploads a signed and stamped confirmation and supporting documents. Each submission is permanently tied to the official. | Must |
| FR-66 | Verifier records the result as Confirmed, Not confirmed or Problem found, or Not completed after 14 days, and the buyer is told. Show the office, date and title statement on the property page. | Must |
| FR-67 | Management can deactivate an official who leaves office and invite the replacement. Show a coverage map of streets, villages and wards with active officials. | Must |

## 8.13 Professionals

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| FR-68 | Oweru registers professionals of three types: Afisa Mipango Miji, planner and surveyor. Record name, type, professional registration number, national ID number, WhatsApp number, regions and districts covered, and status. Professionals receive a login. They cannot self-register. | Must |
| FR-69 | Verifier assigns jobs to an active professional of the right type covering the property's area. The professional is alerted by WhatsApp and can accept or decline in their dashboard. | Must |
| FR-70 | Job types: boundary survey and area measurement for surveyors; official land-use and planning records check for Afisa Mipango Miji; planning review for planners. | Must |
| FR-71 | The professional uploads findings, a report and evidence such as corner points, beacon photos or planning extracts. Each submission is tied to the professional's name and registration number and reviewed by the verifier. | Must |

## 8.14 Market monitoring panel

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| FR-72 | Dashboard for management and the Marketer covering supply, prices, demand, hot areas, speed of sale, deals, conversion, verification levels, free-check results, partner coverage, lister activity and marketing sources, as listed in section 6. | Must |
| FR-73 | Filter every view by date range, region and category, and export to Excel. Never show personal details of buyers or owners. | Must |

## 8.15 Marketing tools

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| FR-74 | Marketer can manage featured listings, homepage banners and content pages such as guides and FAQs. | Must |
| FR-75 | Marketer can send email campaigns only to users who agreed to receive marketing, and see the results of each campaign. WhatsApp marketing is done outside the system in Phase 1. | Should |

## 8.16 Complaints

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| FR-76 | "Lodge a complaint" form available without an account from every property page, deal page, dashboard and the site footer, pre-filled with the property or deal when opened from it. Fields: name, WhatsApp number, role, complaint type, related property or deal, description, evidence upload. | Must |
| FR-77 | Staff can log complaints received through the Oweru WhatsApp support number or email into the same complaints desk. | Must |
| FR-78 | Give every complaint a complaint number, shown on screen at once or sent back by the channel it came in within 1 working day, and route it by type to the Head of Operations, management or the Verifier. | Must |
| FR-79 | Track statuses Received, In review, Waiting for information, Resolved, Under final review and Closed, with a WhatsApp status link for the person who complained. | Must |
| FR-80 | Hold the agent payout automatically while a complaint about that deal is open. | Must |
| FR-81 | Record every outcome with reasons. Allow a request for final review by the Director within 14 days. Show complaint volumes and resolution times to management. | Must |

## 8.17 Operations and compliance

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| FR-82 | Management tools: approve identities, register and approve partners, assign jobs, suspend with reason, manage the rate table and settings. | Must |
| FR-83 | Consent at data collection. Restrict, encrypt and set retention for owner details, identity documents, ownership documents, partner details and payment records. Log every view. Comply with the Personal Data Protection Act 2022. | Must |
| FR-84 | Website and email notifications for leads, viewings, confirmations, payments, payouts, partner jobs, job progress, results and expiry. No text messages (SMS). | Must |
| FR-85 | WhatsApp outbox for staff: the system prepares each WhatsApp message with recipient, text and link; staff send it with one click through WhatsApp Web and mark it sent. Waiting messages are highlighted after 2 working hours. The system never sends WhatsApp automatically. | Must |

# 9. Non-functional requirements

| **Area** | **Requirement** |
|----|----|
| Language | Full Swahili and English interface. Swahili is the default. |
| Platform | Web only in Phase 1. Responsive design for phones, tablets and computers. Supports current Chrome, Safari, Firefox and Edge, including on low-cost Android phones. |
| Site capture | Runs in the phone browser using its location and camera. Requires HTTPS and the user's permission. Clear guidance is shown if permission is refused. |
| Connectivity | Pages usable on slow 3G connections. Large uploads resume after a dropped connection, and forms keep unsent entries so work is not lost. |
| Performance | Search results within 2 seconds on a normal mobile connection. Market panel views within 5 seconds. |
| Security | Encryption in transit and at rest for personal, ownership and payment data. Role-based access. Every staff and partner action logged. |
| Privacy | Personal Data Protection Act 2022. Consent recorded. Retention periods applied. |
| Audit | Verification records, partner submissions, deal records, payment records and evidence are locked once submitted and never deleted, only superseded. |
| Configuration | Rate table, total commission, expiry periods, time limits, fees and daily limits are management settings, changeable without a release. |
| Availability | Target 99.5 percent monthly uptime. |

# 10. Integrations

| **System** | **Purpose** |
|----|----|
| WhatsApp (browser) | Oweru's own number on the free WhatsApp Business app, used through WhatsApp Web. Staff send confirmation links, registration links and alerts from the outbox. Users use click-to-chat buttons. No Meta platform or message charges in Phase 1. Not yet set up: Oweru needs a dedicated number |
| Email | Backup for confirmations, receipts and notifications |
| Bank accounts | Buyer payments to owners and to Oweru, full check fees and agent payouts, all by bank transfer |
| Tax receipts | Tax-compliant electronic receipts (EFD or VFD) for every amount Oweru receives and keeps. Not yet set up: Oweru must register with the Tanzania Revenue Authority. Phase 1 records receipts issued by Oweru's finance team |
| Satellite imagery and maps | Location checks, imagery history, overlap testing. Not yet set up: Oweru must choose and contract a commercial provider. OpenStreetMap is used during development |
| Administrative areas | List of regions, districts, wards, streets and villages used for locality fields and partner matching |
| PDF generation | Free-check reports and full check reports |

# 11. Settings and default values

| **Setting** | **Default** |
|----|----|
| Total commission | 10 percent of the owner's price |
| Commission rate table | See section 5.4. Example bands until set by the Director |
| Agent payout after deal is Won | 3 working days |
| Lister identity verification expiry | 12 months |
| Level 2 location check expiry | 6 months, or on any change to pin, area or photos |
| Level 3 reliance for a transaction | 30 days. Refresh possible up to 6 months, then full re-check |
| Agent supplies owner contact for a full check | 3 working days |
| Owner consent reply | 7 days |
| Local office job time limit | 14 days |
| Professional job time limit | 7 days |
| Free checks per WhatsApp number per day | 5 |
| Lost then sold review window | 6 months |
| Complaint acknowledgement | 1 working day |
| Complaint resolution target | 5 working days for payment and payout. 10 working days for others |
| Request for final review by the Director | Within 14 days of the outcome |
| Full check fee | To be set |

# 12. Success measures

- Verified listers compared with registered listers.

- Active and Level 2 or higher properties.

- Streets, villages and wards covered by an active local official.

- Free checks run, reports downloaded, and free-check to paid-check conversion.

- Qualified leads, lead to viewing, and viewing to deal conversion.

- Deals closed through Oweru, commission earned, and agent payouts made on time.

- Paid full checks completed on time, and those that prevented a bad purchase.

- Complaints resolved within target time.

- Lister retention after 3 and 6 months.

*Listing count is tracked but is not the main measure of success.*

# 13. Assumptions and open decisions

## Assumptions

- Oweru starts with no property, agent, boundary or partner data. The database and the partner network grow with use.

- Owners and agents capture site evidence. Registered partners carry out local office and professional jobs. Oweru verifiers work remotely.

- Buyers, owners and agents have bank accounts.

- Most users and partners have WhatsApp. Email covers those who do not.

- Before launch Oweru sets up a dedicated WhatsApp number, a map provider and tax receipt registration. None of the three exists yet.

- Oweru assigns staff to send WhatsApp outbox messages promptly during working hours.

## Open decisions

| **Decision** | **Proposed** |
|----|----|
| Commission rate table bands and shares | To be set. Examples in section 5.4 |
| Owner listings with no agent | Buyer pays Oweru's share to Oweru and the rest to the owner |
| Payment to local officials and professionals for each job | To be decided |
| Licence needed to receive buyer money and pay agents | Legal advice before launch, including whether a separate client account at a bank is required |
| Full check fee | To be set |
| Legal definition of the Oweru guarantee | Not used publicly until defined |
| Untitled land reaching Level 3 | Yes, with the land type and its weaker protection always stated |
| Foreign buyer warning for village land | Yes, after legal advice |
| Property ID format | To be chosen |
| Dedicated Oweru WhatsApp number on the WhatsApp Business app | Set up before launch and link staff computers to WhatsApp Web |
| Staff who send WhatsApp outbox messages | To be assigned by the Head of Operations |
| Map and satellite imagery provider | Choose and contract before launch. Compare Mapbox, MapTiler, Google Maps Platform and Esri |
| Registration for electronic tax receipts (EFD or VFD) | Register with TRA through a tax adviser before the first payment |
| Data protection lead | To be assigned |
