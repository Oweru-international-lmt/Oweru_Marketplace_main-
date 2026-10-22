# Oweru Marketplace: Software Requirements Document (SRD)

Phase 1 (web). **This is the build specification.** Every screen, endpoint, rule and test traces back to a requirement ID in this document.

| | |
|---|---|
| Source | `docs/backend_authorization/Oweru-Marketplace-SRD-v1.3.docx` (Oweru International Ltd), converted to Markdown for the repository. The wording below is the source text; only the formatting changed. |
| Version | 1.3, 2 October 2026, issued to the development team |
| Read with | [prd.md](prd.md) (the business view), [architecture.md](architecture.md) (how it is built and what is done) |

How to use it:

- Put requirement IDs (for example `LST-05`, `PAY-08`) in branch names, commit messages, test names and code comments that enforce a rule.
- **Must** is required for launch; **Should** may follow soon after.
- A feature is done only when its acceptance tests (the Given, When, Then tables) pass.
- If the .docx is updated, regenerate this file from it rather than editing the text by hand, and note the new version above.

## Project decisions that change this document (22 October 2026)

The product owner decided the following; they win over the text below. Details and research are in [roadmap.md, Project decisions](roadmap.md#project-decisions-22-october-2026).

| ID | Decision | Affects |
|---|---|---|
| D1 | No bulk upload of listings | LST-11, SRD 24 (bulk import screen) |
| D2 | No paid map provider: free Esri World Imagery through a free ArcGIS key, plus open drone imagery where it exists | SRD 2.6, MAP-06, MAP-07 |
| D3 | Tax receipts through TRA left out for now; recording a receipt is optional | SRD 2.6, PAY-11, PAY-14 |
| D4 | Property ID format `OWR-<region postcode>-<number>`, e.g. `OWR-11-04217` | LST-01, SRD 26 |
| D5 | Commission rate table and full check fee start as editable example tables | PAY-01, SRD 9.3, SRD 22, SRD 26 |

---

| **Item** | **Detail** |
|----|----|
| Organisation | Oweru International Ltd |
| Product | Oweru Marketplace |
| Document | Software Requirements Document |
| Version | 1.3 |
| Date | 2 October 2026 |
| Changes in 1.3 | Sign-in and password reset use email address instead of phone number. Every account must have an email address; email and phone number are each unique. Updated: 2.2, 5.1 (ACC-01, ACC-02, ACC-03, ACC-05), 5.3 (new ACC-T2), 14.1, 15, 25 and 26. |
| Status | Issued to the development team |
| Audience | Developers, testers, designers, project manager |
| Companion document | Oweru Marketplace Product Requirements Document v1.6 (the business view) |

## Contents

- [1. Introduction](#1-introduction)
  - [1.1 Purpose](#11-purpose)
  - [1.2 Product in one paragraph](#12-product-in-one-paragraph)
  - [1.3 How to read this document](#13-how-to-read-this-document)
  - [1.4 Glossary](#14-glossary)
- [2. Overall description](#2-overall-description)
  - [2.1 Phase 1 scope](#21-phase-1-scope)
  - [2.2 User classes](#22-user-classes)
  - [2.3 Operating environment](#23-operating-environment)
  - [2.4 Constraints](#24-constraints)
  - [2.5 Assumptions](#25-assumptions)
  - [2.6 Services Oweru must set up before launch](#26-services-oweru-must-set-up-before-launch)
- [3. Recommended architecture](#3-recommended-architecture)
- [4. Roles and permissions](#4-roles-and-permissions)
- [5. Module: Accounts and identity](#5-module-accounts-and-identity)
  - [5.1 Requirements](#51-requirements)
  - [5.2 Lister identity verification](#52-lister-identity-verification)
  - [5.3 Acceptance tests](#53-acceptance-tests)
- [6. Module: Property records and listings](#6-module-property-records-and-listings)
  - [6.1 Requirements](#61-requirements)
  - [6.2 Key data fields](#62-key-data-fields)
  - [6.3 Listing status](#63-listing-status)
  - [6.4 Acceptance tests](#64-acceptance-tests)
- [7. Module: Search and property pages](#7-module-search-and-property-pages)
- [8. Module: Leads and deals](#8-module-leads-and-deals)
- [9. Module: Payments and commission](#9-module-payments-and-commission)
  - [9.1 Calculation rules](#91-calculation-rules)
  - [9.2 Worked example](#92-worked-example)
  - [9.3 Commission rate table](#93-commission-rate-table)
  - [9.4 Requirements](#94-requirements)
  - [9.5 Deal payment status](#95-deal-payment-status)
  - [9.6 Acceptance tests](#96-acceptance-tests)
- [10. Module: Verification ladder](#10-module-verification-ladder)
- [11. Module: Verification jobs](#11-module-verification-jobs)
  - [11.1 Job types](#111-job-types)
  - [11.2 Requirements](#112-requirements)
  - [11.3 Full check job status](#113-full-check-job-status)
  - [11.4 Verification panel on the property page](#114-verification-panel-on-the-property-page)
- [12. Module: Full check](#12-module-full-check)
- [13. Module: Site capture and maps](#13-module-site-capture-and-maps)
- [14. Module: Local officials (Serikali za Mitaa)](#14-module-local-officials-serikali-za-mitaa)
  - [14.1 Flow when an official is registered](#141-flow-when-an-official-is-registered)
  - [14.2 Flow when no official is registered](#142-flow-when-no-official-is-registered)
  - [14.3 The five questions](#143-the-five-questions)
  - [14.4 Requirements](#144-requirements)
  - [14.5 Acceptance tests](#145-acceptance-tests)
- [15. Module: Professionals](#15-module-professionals)
- [16. Module: Free public check](#16-module-free-public-check)
- [17. Module: Complaints desk](#17-module-complaints-desk)
- [18. Module: Market monitoring panel](#18-module-market-monitoring-panel)
- [19. Module: Marketing tools](#19-module-marketing-tools)
- [20. Module: Notifications and WhatsApp](#20-module-notifications-and-whatsapp)
  - [20.1 Four ways the system reaches people](#201-four-ways-the-system-reaches-people)
  - [20.2 The WhatsApp outbox](#202-the-whatsapp-outbox)
  - [20.3 WhatsApp confirmation rules](#203-whatsapp-confirmation-rules)
  - [20.4 Message catalogue](#204-message-catalogue)
  - [20.5 Requirements](#205-requirements)
- [21. Module: Staff administration and settings](#21-module-staff-administration-and-settings)
- [22. Settings catalogue](#22-settings-catalogue)
- [23. Non-functional requirements](#23-non-functional-requirements)
- [24. Screen inventory](#24-screen-inventory)
- [25. Data model summary](#25-data-model-summary)
- [26. Open items that affect development](#26-open-items-that-affect-development)

# 1. Introduction

## 1.1 Purpose

This document tells the development team exactly what to build for Phase 1 of Oweru Marketplace. It turns the business requirements into precise, testable software requirements: who can do what, which screens exist, what data is stored, how every status changes, how money is calculated, and how each feature is tested.

Each module starts with a short "In plain words" box so that anyone, technical or not, can understand what the module is for before reading the detail.

## 1.2 Product in one paragraph

Oweru Marketplace is a Tanzanian web system where buyers find land, houses and commercial property listed by owners or by independent agents. Every property shows honestly what Oweru has checked. Buyers can pay for a full ownership check before they buy, carried out with the help of registered local government officials and professionals. When a deal closes, the buyer pays the owner directly and pays Oweru its share; Oweru keeps its commission and pays the agent. Oweru's team runs the system through staff dashboards, a complaints desk and a market monitoring panel.

## 1.3 How to read this document

- **Requirement IDs** use a module prefix, for example LST-04 is the fourth listing requirement. Use these IDs in tickets, commits and test cases.

- **Must** means required for the Phase 1 launch. Should means wanted, and may be delivered shortly after launch.

- **Business rules** are rules the software must enforce, not advice.

- **Acceptance tests** are written as Given, When, Then. A feature is done only when its tests pass.

- **Settings** marked as configurable must be stored in the database and editable by management without a new release.

- **WhatsApp** wherever a requirement says a message is sent or an alert is given by WhatsApp, it is sent the way section 20.4 lists for that message: usually through the staff WhatsApp outbox. The system never sends WhatsApp automatically in Phase 1.

- **Technology** recommendations in section 3 are recommendations. The team may propose equivalents, but must meet every requirement.

## 1.4 Glossary

| **Term** | **Meaning** |
|----|----|
| Lister | The person who listed a property: the owner or an agent |
| Owner | Legal owner of a property. May sell directly with an account, or through an agent without an account |
| Agent (dalali) | Independent broker who sells a property on behalf of its owner. Not Oweru staff |
| Owner's price | The price the owner wants. Private. Entered by the agent and confirmed by the owner |
| Selling price | The price shown to buyers. On an agent listing it may be higher than the owner's price |
| Partner | A registered local official or professional who receives verification jobs |
| Local official | Mwenyekiti (chairperson) or Mtendaji (executive officer) of a street (Mtaa) or village (Kijiji) under Serikali za Mitaa (local government) |
| Afisa Mipango Miji | Town planning officer. Checks official land-use and planning records |
| Planner | Registered land-use planner. Carries out planning reviews |
| Surveyor | Registered land surveyor. Captures boundaries and measures area on site |
| Management | The Director and the Head of Operations. Both have identical permissions |
| Locality | Region (Mkoa), district (Wilaya), ward (Kata), and street (Mtaa) or village (Kijiji) |
| Verification level | Level 0 to 3, showing how much Oweru has checked a property |
| Full check | The paid Level 3 ownership check a buyer orders before buying |
| Free check | The free public location check anyone can run on any property |
| WhatsApp confirmation | A one-time link sent to the person on WhatsApp by Oweru staff. The person opens it, reads what they are agreeing to and taps Confirm or Decline |
| WhatsApp outbox | Staff screen listing WhatsApp messages the system has prepared. Staff send each one with one click through WhatsApp Web |
| Property Record | The single permanent record for a property, holding all listings, checks and evidence over its life |
| Property ID | Unique Oweru identifier of a Property Record |
| CCRO | Certificate of Customary Right of Occupancy, a document for village land |

# 2. Overall description

## 2.1 Phase 1 scope

| **In scope** | **Out of scope (later phases)** |
|----|----|
| Responsive web system for buyers, listers, partners and staff | Native Android and iOS apps |
| Owner and agent listings, bulk import, leads and deals | Company or agency accounts |
| Verification ladder, full check, free check with PDF report | Refunds of any kind |
| Local officials and professionals with their own dashboards | Referral tracking and rewards |
| Commission calculation, bank payment tracking, agent payouts | Rental properties |
| Complaints desk, market monitoring panel, marketing tools | Text messages (SMS) |
| On-screen, email and WhatsApp (browser) notifications | Automatic WhatsApp messaging through Meta's paid platform. Automatic bank integration |

## 2.2 User classes

| **User class** | **Account type** | **How they get access** |
|----|----|----|
| Buyer | Public | Signs up with email address, phone number and password, and signs in with email and password. Many actions work without an account |
| Owner | Public, or none | Signs up to sell directly. When an agent lists for them, acts only through WhatsApp confirmations |
| Agent | Public | Signs up and chooses "I am an agent" when listing |
| Local official | Partner | Invited by WhatsApp registration link, approved by the Head of Operations |
| Professional | Partner | Created by management. Receives login details by WhatsApp |
| Verifier | Staff | Created by management |
| Marketer | Staff | Created by management |
| Director, Head of Operations | Staff (management) | Created at set-up. Can create all other staff and partner accounts |

## 2.3 Operating environment

- Web only. Must work on current Chrome, Safari, Firefox and Edge, on phones, tablets and computers, including low-cost Android phones.

- Served only over HTTPS. Site capture needs the browser's location and camera, which browsers allow only on HTTPS.

- Interface in Swahili and English. Swahili is the default. Every user-facing text must come from translation files, never hard-coded.

- Must stay usable on slow 3G connections.

## 2.4 Constraints

- No text messages (SMS) anywhere. WhatsApp is ordinary WhatsApp used in the browser: the system prepares messages and people send them (section 20). Email and on-screen notifications are automatic.

- All money moves by bank transfer. The system records and tracks payments; it does not move money itself in Phase 1.

- Oweru starts with no data. Every feature must work with an empty database and grow with use.

- Personal data must be handled under Tanzania's Personal Data Protection Act 2022.

- The word "guarantee" must not appear anywhere in the interface until management enables approved guarantee wording.

## 2.5 Assumptions

- A list of regions, districts and wards is loaded at set-up. Streets and villages are added over time by staff (section 6).

- Oweru has a company bank account for receiving buyer payments and paying agents.

## 2.6 Services Oweru must set up before launch

Oweru does not yet have the three services below. The WhatsApp number can be ready in days. The map provider contract and tax registration can take weeks, so they must be started now. The system is built so that development is not blocked while they are pending.

| **Service** | **What Oweru must do** | **How development continues meanwhile** | **If not ready at launch** |
|----|----|----|----|
| Oweru WhatsApp number | Get a dedicated phone number for Oweru, install the free WhatsApp Business app, set up the business profile, and link WhatsApp Web on the staff computers that will send messages. No Meta approval or message charges are needed | Build the outbox with click-to-chat links, which work with any WhatsApp number, including a test number | Owner confirmations, official registration and task alerts cannot be sent |
| Map and satellite imagery provider | Choose a commercial provider with satellite imagery and a pay-as-you-go plan, and accept its terms for commercial use. Candidates to compare: Mapbox, MapTiler, Google Maps Platform and Esri. Roads and public layers can come from OpenStreetMap data, which is free to use with attribution | Build the map provider-neutral. Use an OpenStreetMap street map in development and switch the provider key at launch | Verifiers and the free check cannot see a satellite view, so location checks and free check verdicts cannot be done properly |
| Tax-compliant electronic receipts | With a tax adviser, register with the Tanzania Revenue Authority for electronic fiscal receipts (EFD or VFD). For VFD, choose a TRA-approved provider that offers a connection for software | Phase 1 records the official receipt number and a copy for each amount, issued by Oweru's finance team outside the system (PAY-11). Automatic issue is added later (PAY-14) | Oweru cannot legally receipt its commission and full check fees |

# 3. Recommended architecture

> **In plain words:** One website serves everyone. What each person sees depends on their role. Behind it sits one database, a file store for photos and documents, and a background worker that sends WhatsApp messages and builds reports.

| **Component** | **Recommendation** | **Why** |
|----|----|----|
| Web front end | Responsive web application, server-rendered or single-page, with mobile-first design | One code base for phones and computers |
| Back end | REST or GraphQL API with role-based access checks on every endpoint | Security is enforced on the server, never only in the browser |
| Database | PostgreSQL with the PostGIS extension | Reliable, and PostGIS handles boundaries, distances and overlap tests |
| File storage | S3-compatible object storage, private by default, served through short-lived signed links | Photos, documents and reports are never publicly listed |
| Background jobs | Job queue with retries | Email sending, PDF building, duplicate checks and expiry checks run in the background |
| Maps | Leaflet or MapLibre, provider-neutral. OpenStreetMap street map in development, commercial satellite provider at launch (section 2.6) | Map views, pins, boundaries and imagery review |
| PDF | Server-side PDF generation from HTML templates | Free check reports, full check reports and the local office confirmation |
| Messaging | One messaging layer with four channels: on screen, email service, WhatsApp outbox and WhatsApp self-service click-to-chat links (section 20) | Can later switch WhatsApp to Meta's platform without touching other modules |
| Hosting | Managed cloud hosting with daily backups and monitoring | Availability and recovery targets in section 23 |

# 4. Roles and permissions

> **In plain words:** Every screen and every action is locked to the roles below. If a role is not listed for an action, the server must refuse it, even if someone tries to call it directly.

| **Action** | **Buyer** | **Owner** | **Agent** | **Local official** | **Professional** | **Verifier** | **Marketer** | **Management** |
|----|----|----|----|----|----|----|----|----|
| Search, view, enquire | Yes | Yes | Yes |  |  |  |  | Yes |
| Create and edit own listings |  | Yes | Yes |  |  |  |  | Yes |
| See owner's price |  | Own | Own listings |  |  |  |  | Yes |
| See owner's contact and bank |  | Own | Own listings |  |  |  |  | Yes |
| Manage leads and deals |  | Own | Own |  |  |  |  | View all |
| Order and pay for a full check | Yes |  |  |  |  |  |  |  |
| Complete assigned verification jobs |  |  |  | Own street | Assigned | Yes |  |  |
| Record verification results |  |  |  |  |  | Yes |  | Yes |
| Approve lister identities |  |  |  |  |  |  |  | Yes |
| Register and approve partners |  |  |  |  |  |  |  | Yes |
| Edit commission rate table |  |  |  |  |  |  |  | Yes |
| Confirm payments, record payouts |  |  |  |  |  |  |  | Yes |
| Lodge a complaint | Yes | Yes | Yes | Yes | Yes |  |  |  |
| Handle complaints |  |  |  |  |  | Verification type |  | All |
| Banners, featured listings, campaigns |  |  |  |  |  |  | Yes | Yes |
| Market monitoring panel |  |  |  |  |  |  | Yes | Yes |
| Send WhatsApp outbox messages |  |  |  |  |  | If granted | If granted | Yes |
| Staff accounts and settings |  |  |  |  |  |  |  | Yes |

*A person may hold only one account per email address and only one per phone number. A public account can both buy and list. Staff and partner accounts are separate from public accounts.*

# 5. Module: Accounts and identity

> **In plain words:** People sign up with their email address, phone number and a password, and sign in with their email and password. Listers prove their phone is theirs by opening a link Oweru sends to it on WhatsApp. Anyone who lists a property proves who they are with their national ID and a live selfie, and Oweru checks it.

## 5.1 Requirements

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| ACC-01 | Sign up with email address, phone number, full name and password. The email address and the phone number must each belong to only one account. A lister's phone number is confirmed when they submit their identity: Oweru sends a confirmation link from the WhatsApp outbox, and the lister opens it. Listings cannot go live until the phone is confirmed. | Must |
| ACC-02 | Sign in with email address and password. Capital letters in the email address are ignored. Lock sign-in for 15 minutes after 5 failed attempts. | Must |
| ACC-03 | Reset a forgotten password through a one-time link sent by email. A user who cannot get into their email contacts Oweru's WhatsApp support number; staff check who they are and send a one-time reset link from the outbox. Links expire after 30 minutes (email) or 24 hours (outbox) and work once. | Must |
| ACC-04 | Passwords are at least 8 characters and stored only as a strong one-way hash. | Must |
| ACC-05 | Every account has an email address. It is the sign-in identifier, is confirmed by an email link, and is used for password reset, receipts and as a backup channel. | Must |
| ACC-06 | Management can create, edit, suspend and deactivate staff accounts and partner accounts. Staff and partners must change their password at first sign-in. | Must |
| ACC-07 | Every account has a language preference, Swahili by default. | Must |
| ACC-08 | A user can see and edit their profile, and request deletion of their account, which management processes subject to records that must be kept by law. | Must |

## 5.2 Lister identity verification

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| IDV-01 | Before a lister's properties can show Level 1, the lister submits: national ID number, a photo of the national ID card, and a live selfie taken through the browser camera. Uploading a selfie from the gallery is not allowed. | Must |
| IDV-02 | The lister states whether they list as an owner or as an agent. One account may hold both kinds of listings. | Must |
| IDV-03 | Management reviews each submission side by side (ID photo and selfie) and approves or rejects it with a reason. The lister is told by WhatsApp. | Must |
| IDV-04 | An approved identity expires after 12 months (configurable). The lister is reminded by WhatsApp 30 days before, and their listings drop from Level 1 if it lapses. | Must |
| IDV-05 | Automatic face matching between the ID photo and the selfie, to assist the reviewer. | Should |
| IDV-06 | Public lister profile: name, photo, areas covered, property types, verification status, time on Oweru, and whether the lister is an owner or an agent. Agent profiles show the fixed text: "Independent agent acting for property owners. Not an employee of Oweru." | Must |

## 5.3 Acceptance tests

| **Test** | **Given** | **When** | **Then** |
|----|----|----|----|
| ACC-T1 | A lister has not opened the phone confirmation link | They try to publish a listing | The system blocks it and offers to request a new link |
| ACC-T2 | An account was registered with the email Asha@Example.com | The user signs in with asha@example.com and the right password, and someone else tries to sign up with ASHA@example.com | Sign-in succeeds, and the second sign-up is refused because the email address is already in use |
| IDV-T1 | A lister tries to upload a selfie from the gallery | They open the selfie step | Only the live camera is offered |
| IDV-T2 | An approved identity is 12 months old | The nightly expiry job runs | Identity is marked expired and affected listings are recalculated below Level 1 where applicable |

# 6. Module: Property records and listings

> **In plain words:** Every property gets one permanent record. Owners and agents create listings on it. An agent enters two prices: what the owner wants, which stays private, and what buyers see. The owner confirms their price and bank account by WhatsApp.

## 6.1 Requirements

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| LST-01 | Every property known to Oweru has one Property Record with a unique Property ID. Listings, free checks and outside full checks all attach to a Property Record. Records are never deleted. | Must |
| LST-02 | Create a listing with: category (land, house, commercial), selling price in TSh, map pin, region, district, ward, street or village, size and unit, title type if known (registered title, residential licence, sale agreement, CCRO, village records, none, unknown), description, features and at least 3 photos. | Must |
| LST-03 | Region, district and ward are chosen from the loaded lists. Street or village is chosen from the list for that ward, or typed in as a new name, which staff then approve and add to the list. | Must |
| LST-04 | The lister chooses "I am the owner" or "I am an agent" for each listing. | Must |
| LST-05 | On an agent listing, the agent also enters privately: owner's full name, owner's WhatsApp number and the owner's price. The system then sends the owner a WhatsApp confirmation showing the property, the owner's price, the 10 percent commission and the amount the owner will receive, and asks for the owner's bank account. | Must |
| LST-06 | While the owner has not confirmed, the listing may go live, but the lead cannot move to Closing. If the owner declines, the listing is suspended and the agent is told. | Must |
| LST-07 | The selling price may never be lower than the owner's price. To go lower, the agent enters a new owner's price, which the owner must confirm again. | Must |
| LST-08 | On an owner listing, the owner's price and the selling price are the same value. The owner adds their own bank account in their profile. | Must |
| LST-09 | Show the agent a live payout preview while entering prices, using the commission rate table (section 9). | Must |
| LST-10 | Listing statuses and transitions follow section 6.3. Every change is logged with user and time. | Must |
| LST-11 | Bulk import from an Oweru Excel or CSV template, with photos uploaded as a batch and matched by a row reference. The system shows a validation report and publishes nothing until the lister confirms. Management can import on a lister's behalf. | Must |
| LST-12 | Duplicate check on create, edit and import: flag any Property Record whose pin is within 50 metres (configurable), with size within 10 percent, or with a near-identical photo. Duplicates are linked to one Property Record and flagged for staff review. They are never blocked automatically. | Must |
| LST-13 | Photos are resized and compressed on upload. Original files are kept privately for evidence. | Must |

## 6.2 Key data fields

| **Entity** | **Main fields** |
|----|----|
| PropertyRecord | property_id, category, pin (point), boundary (polygon, optional), locality ids, stated size, title type, created_at |
| Listing | listing_id, property_id, lister_id, lister_kind (owner or agent), selling_price, owner_price, rate_table_version, status, description, features, created_at |
| OwnerContact | listing_id, owner_name, owner_whatsapp, owner_bank_account, owner_confirmed_at, confirmation_id |
| Locality | region, district, ward, street_or_village (with approved flag) |
| Media | media_id, owner entity, file key, source (camera or gallery), captured location, captured time, device, hash |

## 6.3 Listing status

| **Status** | **Meaning** | **Moves to** |
|----|----|----|
| Draft | Being prepared, not public | Active |
| Active | Public and searchable | Under offer, Withdrawn, Suspended |
| Under offer | A lead is at Closing. Still visible, marked Under offer | Sold, Active |
| Sold | Deal marked Won. Not searchable | None |
| Withdrawn | Removed by the lister | Active |
| Suspended | Removed by management with a reason | Active (by management only) |

## 6.4 Acceptance tests

| **Test** | **Given** | **When** | **Then** |
|----|----|----|----|
| LST-T1 | An agent listing with owner's price 100,000,000 | The agent enters a selling price of 95,000,000 | The system refuses and explains that the owner must confirm a lower owner's price first |
| LST-T2 | A buyer is viewing an agent listing | The page loads | No owner name, contact, bank details or owner's price appear anywhere in the page or its data |
| LST-T3 | A new listing has a pin 30 metres from an existing record and similar size | It is saved | It is linked to the existing Property Record and flagged for review, and it still goes live |

# 7. Module: Search and property pages

> **In plain words:** Buyers search by place, type, price and how well a property has been checked, on a list or a map. Each property page shows its photos, price, place, who listed it and exactly what has been checked.

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| SRC-01 | Search without an account. Filters: category, region, district, ward, price range, size range, title type and minimum verification level. Sort by newest, price and verification level. | Must |
| SRC-02 | List view and map view. The map shows approximate positions only, rounded to about 200 metres (configurable), never the exact pin. | Must |
| SRC-03 | Property page: photos, selling price, locality, size, description, features, approximate map, lister profile, verification panel (section 11.4) and buttons for enquiry, WhatsApp contact, viewing request and full check. | Must |
| SRC-04 | Featured listings chosen by the Marketer appear first in a marked "Featured" area, never mixed silently into normal results. | Must |
| SRC-05 | Search results within 2 seconds on a normal mobile connection. | Must |
| SRC-06 | Every search, filter use, page view and enquiry is recorded anonymously for the market monitoring panel. | Must |

# 8. Module: Leads and deals

> **In plain words:** When a buyer shows interest, the lister gets a lead. The lister moves it through the stages of a sale. At Closing, the final price is agreed, the buyer is offered a full check, and the payments are arranged. A deal is Won only when everyone has confirmed the money arrived and the signed sale agreement is uploaded.

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| LEAD-01 | An enquiry, WhatsApp contact click or viewing request creates a lead for the lister, with the buyer's name and WhatsApp number. The lister is notified by WhatsApp. | Must |
| LEAD-02 | Lead stages: New, Contacted, Viewing, Negotiation, Closing, Won, Lost. The lister moves leads forward or to Lost, with notes and follow-up dates. | Must |
| LEAD-03 | Moving to Closing requires: the final selling price, and on agent listings the owner's confirmation (LST-05). The listing becomes Under offer and the buyer is offered the full check. | Must |
| LEAD-04 | At Closing, the system creates a Deal with the payment breakdown (section 9) and sends the buyer the payment instructions. | Must |
| LEAD-05 | A lead becomes Won only when all of these are recorded: owner confirmed receipt, management confirmed Oweru's receipt, signed sale agreement uploaded, and lister confirmation that the agreement states the exact final selling price. Management checks the agreement price before approving. | Must |
| LEAD-06 | A private customer list for each lister, built from their leads, with notes. | Must |
| LEAD-07 | Performance figures per listing and overall: views, enquiries, viewings, response time, stage conversion, won deals. | Should |
| LEAD-08 | If a lead is marked Lost and the same property is later marked sold to the same buyer within 6 months (configurable), flag it for management review. | Must |

# 9. Module: Payments and commission

> **In plain words:** On an agent listing, the owner gets 90 percent of their price straight from the buyer. The buyer pays everything else to Oweru. Oweru keeps its share from the rate table and pays the agent the rest. Nobody moves money through the system in Phase 1: buyers pay by bank transfer and upload the slip, and management confirms.

## 9.1 Calculation rules

Let O be the owner's price, S the final selling price, T the total commission rate (default 10 percent, configurable) and X Oweru's rate from the rate table band that contains S.

| **Amount** | **Agent listing** | **Owner listing (O equals S)** |
|----|----|----|
| Buyer pays owner | O x (1 - T) | S x (1 - X) |
| Buyer pays Oweru | (S - O) + O x T | S x X |
| Oweru keeps | O x X | S x X |
| Agent payout | O x (T - X) + (S - O) | None |
| Check | Buyer pays owner + buyer pays Oweru = S | Buyer pays owner + buyer pays Oweru = S |

- All amounts are whole Tanzanian shillings. Any rounding difference is added to or taken from Oweru's kept amount, so the totals always equal S exactly.

- The rate table version is fixed when the listing is created. The band inside that version is chosen using the final selling price at Closing.

- Every breakdown is stored on the Deal and never recalculated after the lead is Won.

## 9.2 Worked example

| **Input or result**                               | **Value (TSh)** |
|---------------------------------------------------|-----------------|
| Owner's price O                                   | 100,000,000     |
| Selling price S                                   | 120,000,000     |
| Band for 120,000,000: Oweru X = 3%, total T = 10% |                 |
| Buyer pays owner                                  | 90,000,000      |
| Buyer pays Oweru                                  | 30,000,000      |
| Oweru keeps                                       | 3,000,000       |
| Agent payout                                      | 27,000,000      |

## 9.3 Commission rate table

Management maintains the table. Each version has bands with a lower and upper selling price, Oweru's rate and the agent's rate, which must add up to T. Bands must not overlap or leave gaps. Example values until the Director sets them:

| **Selling price (TSh)**    | **Oweru** | **Agent** | **Total** |
|----------------------------|-----------|-----------|-----------|
| 0 to 50,000,000            | 4%        | 6%        | 10%       |
| 50,000,001 to 200,000,000  | 3%        | 7%        | 10%       |
| 200,000,001 to 500,000,000 | 2.5%      | 7.5%      | 10%       |
| Above 500,000,000          | 2%        | 8%        | 10%       |

## 9.4 Requirements

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| PAY-01 | Management can create a new version of the rate table, which applies to listings created after it is published. Old versions stay stored and unchanged. | Must |
| PAY-02 | Agents and owners can view the current rate table in their dashboard and on the listing form. | Must |
| PAY-03 | Calculate and store the breakdown of section 9.1 on every Deal at Closing, and recalculate only if the final selling price changes before any payment is uploaded. | Must |
| PAY-04 | Each lister stores a bank account for receiving money (bank name, account name, account number, branch). On agent listings the owner's account is captured through the owner's WhatsApp confirmation. | Must |
| PAY-05 | Bank details are private. They are shown only to the account holder, to management, and to the buyer of an active Deal on the payment instructions screen. | Must |
| PAY-06 | Payment instructions show the buyer two transfers: amount into the owner's account, and amount into Oweru's account with a unique payment reference. | Must |
| PAY-07 | The buyer uploads a bank slip or transfer confirmation for each transfer. | Must |
| PAY-08 | The owner confirms receipt of their amount: in their account on owner listings, or by WhatsApp confirmation on agent listings. | Must |
| PAY-09 | Management confirms Oweru's receipt after checking Oweru's bank statement, and records the bank reference. | Must |
| PAY-10 | After the lead is Won, the agent payout is due within 3 working days (configurable). Management records the payout with bank reference and proof. The agent sees status: Pending, Due, Paid or On hold. | Must |
| PAY-11 | For every amount Oweru receives and keeps, management records the official tax receipt number (EFD or VFD) and uploads a copy. The receipt is issued by Oweru's finance team outside the system in Phase 1. The system also sends an Oweru payment acknowledgement, clearly marked "This is not a tax receipt". | Must |
| PAY-12 | Management can put a payout on hold with a reason. A payout is held automatically while a complaint about its deal is open. | Must |
| PAY-13 | Buyers pay for a full check by bank transfer to Oweru with a payment reference and upload the slip. Management confirms receipt before the check starts. | Must |
| PAY-14 | Issue tax receipts automatically through a TRA-approved VFD provider's connection, once Oweru is registered. | Should |

## 9.5 Deal payment status

| **Status** | **Meaning** |
|----|----|
| Awaiting payment | Deal created at Closing. Instructions sent to the buyer |
| Proof uploaded | Buyer uploaded one or both slips |
| Owner confirmed | Owner confirmed receipt of their amount |
| Oweru confirmed | Management confirmed Oweru's receipt |
| Complete | Both confirmed and the sale agreement approved. Lead becomes Won |
| Payout paid | Agent payout recorded as paid |

## 9.6 Acceptance tests

| **Test** | **Given** | **When** | **Then** |
|----|----|----|----|
| PAY-T1 | O = 100,000,000, S = 120,000,000, band 3% and T = 10% | The deal reaches Closing | Owner 90,000,000; Oweru collects 30,000,000; Oweru keeps 3,000,000; agent 27,000,000 |
| PAY-T2 | An owner listing at S = 100,000,000 in the 3% band | The deal reaches Closing | Buyer pays owner 97,000,000 and Oweru 3,000,000 |
| PAY-T3 | The rate table changed after a listing was created | That listing's deal is calculated | The old table version is used |
| PAY-T4 | A complaint is open on a deal | Management tries to record the payout | The system blocks it until the complaint is closed |

# 10. Module: Verification ladder

> **In plain words:** Every property shows one level from 0 to 3. The system works it out from the checks that are done and still valid. Nobody can set it by hand. Each level has fixed wording that must be used exactly.

| **Level** | **Condition** | **Exact label** |
|----|----|----|
| 3 Oweru Verified | A full check passed and is still valid | Oweru Verified: full check completed \[date\]. Valid until \[date\]. |
| 2 Location Checked | A location check passed and is still valid | Location and details checked by Oweru. This is not ownership verification. |
| 1 Lister Verified | The lister's identity is approved and not expired | Listed by \[name\], identity verified by Oweru. |
| 0 Listed | None of the above | Listed by \[name\]. Not verified by Oweru. |

- The level shown is the highest level whose condition is met.

- On owner listings below Level 3, add: "\[name\] states they are the owner. Ownership has not been verified."

- The Oweru Verified name, colour and badge style are reserved for Level 3 and must not be reused elsewhere.

- The phrase "Oweru Agent" must never appear in the interface.

- The level is recalculated whenever a check is completed or expires, and by a nightly job.

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| LVL-01 | Compute and store the level of every listing using the rules above, and recalculate on every relevant event and nightly. | Must |
| LVL-02 | Store all labels as fixed translation strings approved by management. Listers cannot edit them. | Must |

# 11. Module: Verification jobs

> **In plain words:** Every check is a job with a responsible Oweru verifier, a checklist, tasks for partners where needed, evidence and a result. Everything is recorded: who did what, when, and on what evidence.

## 11.1 Job types

| **Job type** | **Started by** | **Tasks inside** | **Result** |
|----|----|----|----|
| Location check | Automatically for new listings, done by a verifier | Verifier desk review | Passed or Failed. Passed gives Level 2 |
| Full check | Buyer order and payment | Owner consent, site capture, local office task, professional tasks, Land Registry search, verifier review | Passed, Problem found or Not completed |
| Outside full check | Buyer order for a property not listed on Oweru | Same as the full check | Same as the full check |

## 11.2 Requirements

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| VER-01 | Every job stores: type, property, responsible verifier, checklist items, tasks, evidence, status history, result, expiry date and audit log. | Must |
| VER-02 | Location check checklist: pin is on land inside Tanzania; photos fit the satellite view; no conflicting duplicate; no gross mismatch between description and place. The verifier works from one screen showing the map, satellite imagery, photos and duplicate candidates. | Must |
| VER-03 | Every evidence item and every answer records who created it, their role, when, and from which device. | Must |
| VER-04 | Once a task or job is submitted, its evidence is locked. Corrections are added as new versions; nothing is overwritten or deleted. | Must |
| VER-05 | Results expire: location check after 6 months or when the pin, area or photos change; full check can be relied on for 30 days, refreshable up to 6 months (all configurable). Listers are told by WhatsApp before expiry. | Must |
| VER-06 | A partner is never assigned a task on a property they own, list, or have declared a relationship to. The system blocks it. | Must |
| VER-07 | An adverse full check result goes only to the paying buyer, flags the Property Record internally and blocks Level 3. No public fraud label is shown. | Must |

## 11.3 Full check job status

| **Status** | **Meaning** |
|----|----|
| Awaiting payment | Buyer ordered, payment not yet confirmed |
| Awaiting consent | Paid. Waiting for the owner's consent, up to 7 days |
| In progress | Consent given. Tasks running |
| Under review | All tasks submitted. Verifier reviewing |
| Passed | All checks passed. Property reaches Level 3 |
| Problem found | An issue was found. Report sent to buyer |
| Not completed | Owner refused or did not respond, or a task timed out. Buyer told |

## 11.4 Verification panel on the property page

For every check the panel shows: check name, result, date, who carried it out (name and role for partners, staff reference for verifiers), what was not checked, and expiry date. For untitled land it adds: "No registered title. Local office records give less protection than a title."

# 12. Module: Full check

> **In plain words:** A buyer about to buy pays for a full check. The owner agrees, the boundary is captured, the local office and any needed professionals give their answers, and an Oweru verifier puts it all together into a written report.

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| FUL-01 | A buyer orders a full check from a property page, or for an outside property by entering its details and locality. The fee and what the check covers are shown before ordering. | Must |
| FUL-02 | Owner consent: on owner listings, the owner accepts in their account; on agent listings, the owner receives a WhatsApp confirmation. The agent must provide the owner's contact if it is missing within 3 working days. No reply within 7 days means Not completed. | Must |
| FUL-03 | Site capture task for the owner or agent, or a surveyor task when the verifier chooses (section 13). | Must |
| FUL-04 | Local office task sent automatically to the registered official for the property's street or village (section 14). | Must |
| FUL-05 | Professional tasks assigned by the verifier where needed (section 15). | Must |
| FUL-06 | Verifier records the Land Registry search result where the land has a registered title. | Must |
| FUL-07 | Verifier writes the risk assessment and sets the result. The system generates the report as a PDF and sends the buyer a download link by WhatsApp. | Must |

# 13. Module: Site capture and maps

> **In plain words:** The owner, the agent or a surveyor walks to each corner of the plot with a phone and taps to record its position. They add photos and a short video. The system joins the corners into a boundary, measures the area and checks for overlaps.

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| MAP-01 | Corner capture in the phone browser: the user stands at each corner and taps Record. The system stores latitude, longitude, accuracy, time and device. Points with accuracy worse than 10 metres (configurable) are rejected with a request to wait and retry. | Must |
| MAP-02 | At least 3 corners are required. The system joins them into a boundary polygon and calculates the area in square metres. | Must |
| MAP-03 | Photos and video can be taken with the camera or chosen from the gallery. The system records the source, reads any location and time stored in the file, and flags items with no location, a location more than 200 metres from the plot, or a date older than 30 days (all configurable). | Must |
| MAP-04 | Compare the measured area with the stated area and flag differences above 10 percent (configurable). | Must |
| MAP-05 | Test the boundary for overlap with other boundaries on record and with loaded public layers such as roads and reserves, and show the verifier any overlap on the map. | Must |
| MAP-06 | Show current satellite imagery from the chosen provider (section 2.6). Until a provider is in place, show the OpenStreetMap street map and mark satellite-dependent checks as unavailable. | Must |
| MAP-07 | Show historical imagery where the chosen provider supports it. | Should |
| MAP-08 | Record site risks (flooding, wetland, steep ground, power lines, road proximity) and development context (distance to tarmac road, water, power, school, market). | Should |
| MAP-09 | Never state or imply that maps or imagery prove ownership. | Must |

# 14. Module: Local officials (Serikali za Mitaa)

> **In plain words:** Every property records its street or village. The system sends the local office check to the official registered for that street. If nobody is registered yet, Oweru sends the office a WhatsApp link to register. Once registered, the official has a dashboard and receives every future job for their street.

## 14.1 Flow when an official is registered

1.  A full check reaches the local office task.

2.  The system finds the active officials registered for the property's street or village.

3.  The task appears in their dashboards and each receives a WhatsApp alert.

4.  An official opens the task, answers the five questions and uploads a signed and stamped confirmation and any documents.

5.  The first complete submission completes the task. Other officials of the same street see it as done.

6.  The verifier reviews it and phones the official only if something does not match.

## 14.2 Flow when no official is registered

1.  The system marks the task "Needs official" and alerts management.

2.  Staff obtain the office's WhatsApp number through the ward or council office and enter it. A number given by the owner or agent must never be used.

3.  The system sends a registration link by WhatsApp. It works once and expires after 14 days (configurable).

4.  The official registers: full name, position (Mwenyekiti or Mtendaji), national ID number, live photo through the camera, office locality, office stamp photo, email address and a password.

5.  The Head of Operations confirms the official with the ward or council office and approves. The official can then sign in.

6.  Waiting tasks for that street or village move into the official's dashboard, and the flow in 14.1 continues.

## 14.3 The five questions

| **No.** | **Question (shown in Swahili and English)** | **Answer type** |
|----|----|----|
| 1 | Is this plot in your Mtaa or village? | Yes or No |
| 2 | Do you know \[owner name\] as the owner of this plot? | Yes or No, with comment |
| 3 | Has this plot been sold or given to anyone else? | Yes or No, with comment |
| 4 | Is there any dispute over this plot? | Yes or No, with comment |
| 5 | Are the boundaries agreed with the neighbours? | Yes or No, with comment |

## 14.4 Requirements

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| LOC-01 | Store officials with: name, position, national ID number, photo, WhatsApp number, locality, stamp photo, status (Invited, Awaiting approval, Active, Deactivated) and the staff member who confirmed them. | Must |
| LOC-02 | Route each local office task automatically by exact match on street or village. | Must |
| LOC-03 | Official dashboard: list of open and completed tasks for their street or village, task detail with property locality, owner name, approximate map and the five questions, and upload of the signed and stamped confirmation. | Must |
| LOC-04 | Every submission is permanently tied to the official who made it and locked once submitted. | Must |
| LOC-05 | A task not completed within 14 days (configurable) becomes Not completed, and the buyer is told. | Must |
| LOC-06 | Management can deactivate an official and invite a replacement. Deactivated officials cannot sign in and receive no tasks. | Must |
| LOC-07 | Coverage map for management showing streets, villages and wards with active officials. | Must |

## 14.5 Acceptance tests

| **Test** | **Given** | **When** | **Then** |
|----|----|----|----|
| LOC-T1 | An active official is registered for Mtaa Mbezi A | A full check reaches the local office task for a plot in Mbezi A | The task appears in that official's dashboard and a WhatsApp alert is sent |
| LOC-T2 | No official is registered for the property's street | The local office task starts | The task shows "Needs official" and management is alerted |
| LOC-T3 | An official owns the plot being checked | The task is routed | The official is excluded and the task goes to another official or to "Needs official" |

# 15. Module: Professionals

> **In plain words:** Oweru registers three kinds of professionals and gives them a login: Afisa Mipango Miji, planners and surveyors. The verifier sends them jobs in their area. They accept, do the work and upload their report.

| **Type** | **Task they receive** | **What they submit** |
|----|----|----|
| Afisa Mipango Miji | Official land-use and planning records check | Permitted use, planned roads or reserves affecting the plot, supporting extracts |
| Planner | Planning review | Layout, development restrictions and planning context, with a short report |
| Surveyor | Boundary survey | Corner points captured on site, beacon photos, measured area, overlap notes |

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| PRO-01 | Management registers professionals with: name, type, professional registration number, national ID number, WhatsApp number, email address, regions and districts covered, and status. The system sends login details by WhatsApp. | Must |
| PRO-02 | The verifier assigns a task by choosing from active professionals of the right type who cover the property's district. | Must |
| PRO-03 | The professional receives a WhatsApp alert and accepts or declines in their dashboard. A declined task returns to the verifier. | Must |
| PRO-04 | The professional completes the task within 7 days (configurable), uploading findings, a report and evidence. Surveyors use the site capture tool in section 13. | Must |
| PRO-05 | Each submission is tied to the professional's name and registration number and locked once submitted. | Must |

# 16. Module: Free public check

> **In plain words:** Anyone can check any property for free by dropping a pin and describing it. They give their WhatsApp number, see the result on screen, download the PDF report and can send the link to their own WhatsApp on WhatsApp. It never says who owns the land.

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| FRC-01 | Input: map pin, stated description (size, category, claims such as "beachfront"), optional photos, optional link to an outside listing, and the user's WhatsApp number. | Must |
| FRC-02 | Automatic verdicts: location exists on land in Tanzania; duplicates found on Oweru records; photo location mismatch; gross location mismatch with the description. | Must |
| FRC-03 | Show the verdict on screen with a Download PDF button, and a "Send to my WhatsApp" button that opens the user's own WhatsApp with the report link ready to send to themselves. Email a copy if an address is given. The link works for 30 days (configurable). | Must |
| FRC-04 | The report contains a reference number, date, details as entered, each verdict in plain words, the statement "This is not ownership verification" and how to order the full check. It never contains coordinates, boundaries or the method. | Must |
| FRC-05 | Save each submission as an outside Property Record and register the user as a lead for Oweru. | Must |
| FRC-06 | Limit 5 checks per WhatsApp number per day (configurable). | Must |

# 17. Module: Complaints desk

> **In plain words:** Anyone can complain through the website, WhatsApp or email. Every complaint gets a number, goes to the right person, and is tracked until closed. Management settles conflicts. The Director gives the final word if the person is still unhappy.

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| CMP-01 | "Lodge a complaint" form without sign-in, reachable from every property page, deal page, dashboard and the site footer, pre-filled with the property or deal where relevant. Fields: name, WhatsApp number, role, type, related property or deal, description, evidence files. | Must |
| CMP-02 | Staff can log complaints received by WhatsApp or email into the same desk. | Must |
| CMP-03 | Each complaint gets a number, shown on screen at once. Complaints lodged by WhatsApp or email get their number by the same channel within 1 working day. | Must |
| CMP-04 | Routing by type: fake or wrong listing and other to Head of Operations; conduct, payment or payout, and privacy to management; verification result to the verifier first, then management. | Must |
| CMP-05 | Statuses: Received, In review, Waiting for information, Resolved, Under final review, Closed. The person can see the status through a WhatsApp link. | Must |
| CMP-06 | An open complaint on a deal puts its agent payout on hold automatically. | Must |
| CMP-07 | Outcome and reasons are recorded and sent to the person. A final review by the Director can be requested within 14 days. | Must |
| CMP-08 | Targets: payment and payout complaints resolved within 5 working days, others within 10. Overdue complaints are highlighted to management. | Must |

# 18. Module: Market monitoring panel

> **In plain words:** A dashboard for management and the Marketer showing what is on the market, what people are searching for, what sells, where and for how much.

| **Metric** | **Definition** |
|----|----|
| Active listings | Listings with status Active or Under offer, by region, district, ward and category |
| Average and median selling price | Of active listings, by area and category, per month |
| Price per square metre | Selling price divided by size in square metres, for listings with size in square metres or converted |
| Demand | Searches, filter uses, property views and enquiries by area, category and price range |
| Hot areas | Map heat layer of searches, enquiries and won deals |
| Time to first enquiry | Days from listing going Active to its first lead |
| Time to sale | Days from listing going Active to Sold |
| Deal value and discount | Final selling price of won deals, and difference from the listed selling price |
| Conversion | Enquiry to Viewing, Viewing to Closing, Closing to Won |
| Verification mix | Share of active listings at each level |
| Free check results | Checks run and mismatches found, by area |
| Partner coverage | Streets and villages with active officials; districts covered by each professional type |
| Lister activity | New and active listers, listings per lister, lead response time |
| Marketing sources | Where visitors and leads came from, and campaign results |

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| MON-01 | Show all metrics above with filters for date range, region, district and category. | Must |
| MON-02 | Export any view to Excel. | Must |
| MON-03 | Never show names, phone numbers or other personal details of buyers or owners in the panel. | Must |
| MON-04 | Panel views load within 5 seconds. Heavy figures may be pre-calculated nightly. | Must |

# 19. Module: Marketing tools

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| MAR-01 | Marketer can choose featured listings, with start and end dates. | Must |
| MAR-02 | Marketer can manage homepage banners and content pages such as guides and FAQs, in Swahili and English. | Must |
| MAR-03 | Marketer can send email campaigns only to users who agreed to receive marketing, and see delivery and click results. WhatsApp marketing is done outside the system in Phase 1. | Should |
| MAR-04 | Every link shared by marketing carries a source tag so the market panel can report where visitors came from. | Must |

# 20. Module: Notifications and WhatsApp

> **In plain words:** Phase 1 uses ordinary WhatsApp opened in the browser (WhatsApp Web), not Meta's paid business platform. The system never sends a WhatsApp message by itself. It prepares each message, and a person sends it with one click: either Oweru staff from Oweru's official WhatsApp number, or the user from their own WhatsApp. Everything important is also shown on screen and sent by email where the person has an email address.

## 20.1 Four ways the system reaches people

| **Channel** | **How it works** | **Used for** |
|----|----|----|
| On screen | Notifications list and banners inside the website, shown when the person signs in or is on the page | Everything. This is the only channel that always works |
| Email | Sent automatically by the system | Everything, where the person has an email address |
| WhatsApp outbox (staff) | The system queues the message. Staff open the outbox, click Send, WhatsApp Web opens a chat with the recipient and the message already written, and staff press send | Messages to people without an account or who must act from outside: owners, local offices, partners, complainants |
| WhatsApp self-service | A button opens the user's own WhatsApp with a chat and message already written, and the user presses send | Contacting a lister, sharing a free check report, a lister sharing payment instructions with a buyer |

## 20.2 The WhatsApp outbox

- Oweru uses one official WhatsApp number on the free WhatsApp Business app, linked to WhatsApp Web on the computers of staff who send messages.

- The outbox screen lists waiting messages with: recipient name and number, purpose, the full message in the recipient's language, and any link.

- Clicking Send opens a WhatsApp click-to-chat link (wa.me) with the recipient's number and the message pre-filled. The staff member presses send in WhatsApp, then clicks Mark as sent in the outbox.

- Messages waiting longer than 2 working hours (configurable) are highlighted, and management sees the waiting count on its dashboard.

- Every outbox item records who created it, who sent it and when.

*Rules: one message per click, always sent by a person. No automation tools, scripts or bulk senders may be used with Oweru's WhatsApp number, because WhatsApp bans numbers used that way. When message volume grows too large for staff, Oweru can move to Meta's WhatsApp Business Platform, which the messaging layer allows without changing other modules.*

## 20.3 WhatsApp confirmation rules

- Each confirmation link contains a random single-use token, works once, and expires after 7 days (configurable).

- Confirmation links to owners and partners are always sent from the Oweru outbox, never handed to the agent to send.

- The confirmation page shows exactly what is being agreed, for example property, owner's price, commission, amount to receive and bank account.

- The page offers Confirm and Decline. The system stores the decision, time, phone number the link was sent to, IP address and browser.

- The owner's number must differ from the agent's own number. The system flags an owner number used by several different agents for review.

## 20.4 Message catalogue

| **Message** | **Sent to** | **Trigger** | **How sent** |
|----|----|----|----|
| Confirm your phone number | Lister | Identity submitted | Outbox |
| Password reset link | User | Reset request | Email, or outbox after a request to Oweru's support number |
| Identity approved or rejected | Lister | Management decision | On screen and email |
| Confirm your price and bank account | Owner | Agent listing created or owner's price changed | Outbox |
| New lead | Lister | Enquiry or viewing request | On screen and email |
| Contact the lister | Lister | Buyer taps WhatsApp on a property page | Self-service by the buyer |
| Payment instructions | Buyer | Deal reaches Closing | On screen and email. Lister can share by self-service |
| Confirm you received payment | Owner | Buyer uploads proof of the owner payment | Outbox (agent listings) or on screen (owner listings) |
| Payout paid | Agent | Management records payout | On screen and email |
| Consent to a full check | Owner | Full check payment confirmed | Outbox (agent listings) or on screen (owner listings) |
| Your full check report is ready | Buyer | Full check result set | On screen and email |
| Register as local official | Local office | Staff send registration link | Outbox |
| New verification task | Local official or professional | Task assigned | Outbox, plus on screen |
| Professional login details | Professional | Account created | Outbox |
| Your free check report | Free check user | Free check completed | On screen download, and self-service share to the user's own WhatsApp |
| Complaint number | Complainant | Complaint lodged | On screen at once, plus outbox if lodged by WhatsApp |
| Complaint update and outcome | Complainant | Status change | Outbox and email |
| Verification expiring soon | Lister | 30 days before expiry | On screen and email |

## 20.5 Requirements

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| NTF-01 | All messages go through one messaging layer with four channels: on screen, email, WhatsApp outbox and WhatsApp self-service. Each message in section 20.4 uses the channels listed. | Must |
| NTF-02 | WhatsApp outbox screen for staff with send permission, as described in section 20.2, including Mark as sent, waiting-time highlight and a sent history. | Must |
| NTF-03 | WhatsApp self-service buttons open a click-to-chat link with the number and message pre-filled. | Must |
| NTF-04 | Message texts are stored as editable settings in Swahili and English. | Must |
| NTF-05 | Never send text messages (SMS). Never send WhatsApp messages automatically in Phase 1. | Must |
| NTF-06 | Log every email sent or failed, and every outbox item created and sent. | Must |
| NTF-07 | The messaging layer allows a later switch of the WhatsApp outbox to Meta's WhatsApp Business Platform without changing other modules. | Should |

# 21. Module: Staff administration and settings

| **ID** | **Requirement** | **Priority** |
|----|----|----|
| ADM-01 | Management dashboard with queues: identities to approve, listings flagged, duplicates, partner approvals, tasks needing an official, payments to confirm, payouts due, complaints by status. | Must |
| ADM-02 | Management can suspend or restore any listing or account, always with a recorded reason. | Must |
| ADM-03 | Management can add approved streets and villages to the locality lists. | Must |
| ADM-04 | All settings in section 22 are editable by management with a change log. | Must |
| ADM-05 | Every staff and partner action is written to an audit log that cannot be edited. | Must |

# 22. Settings catalogue

| **Setting** | **Default** | **Used by** |
|----|----|----|
| Total commission rate T | 10 percent | PAY |
| Commission rate table | Section 9.3 example bands | PAY |
| Agent payout due | 3 working days after Won | PAY |
| Lister identity expiry | 12 months | IDV |
| Location check expiry | 6 months | VER |
| Full check reliance / refresh limit | 30 days / 6 months | VER |
| Owner consent reply | 7 days | FUL |
| Agent supplies owner contact | 3 working days | FUL |
| Local office task limit | 14 days | LOC |
| Official registration link expiry | 14 days | LOC |
| Professional task limit | 7 days | PRO |
| WhatsApp confirmation link expiry | 7 days | NTF |
| Outbox waiting highlight | 2 working hours | NTF |
| Free check daily limit | 5 per WhatsApp number | FRC |
| Free check report link validity | 30 days | FRC |
| Duplicate pin distance / size difference | 50 metres / 10 percent | LST |
| Corner point accuracy limit | 10 metres | MAP |
| Gallery photo distance / age flag | 200 metres / 30 days | MAP |
| Area difference flag | 10 percent | MAP |
| Public map rounding | About 200 metres | SRC |
| Lost then sold review window | 6 months | LEAD |
| Complaint acknowledgement / resolution | 1 working day / 5 or 10 working days | CMP |
| Final review request window | 14 days | CMP |
| Full check fee | To be set by the Director | FUL |

# 23. Non-functional requirements

| **ID** | **Area** | **Requirement** |
|----|----|----|
| NFR-01 | Performance | Search under 2 seconds; property page under 3 seconds; market panel under 5 seconds, on a normal mobile connection |
| NFR-02 | Slow networks | Pages usable on 3G. Images compressed and lazy-loaded. Uploads resume after a dropped connection. Forms keep unsent entries |
| NFR-03 | Security | HTTPS only; role checks on every server request; protection against the OWASP Top 10; rate limiting on sign-in, confirmations and the free check |
| NFR-04 | Data protection | Personal, identity, ownership, bank and payment data encrypted at rest; files private with signed links; consent recorded; retention periods applied; every view of sensitive data logged |
| NFR-05 | Audit | Verification, partner, deal and payment records are append-only. Nothing is deleted; corrections are new versions |
| NFR-06 | Availability | 99.5 percent monthly uptime |
| NFR-07 | Backup | Full database backup daily, kept 30 days; file storage replicated; restore tested every quarter |
| NFR-08 | Monitoring | Error tracking, uptime alerts, failed emails, and WhatsApp outbox items waiting too long |
| NFR-09 | Language | Swahili and English for all screens, messages, PDFs and emails. Swahili default |
| NFR-10 | Accessibility | Readable text sizes, sufficient contrast, keyboard use and labelled form fields, following WCAG 2.1 AA as a guide |
| NFR-11 | Browsers | Current Chrome, Safari, Firefox and Edge, including Chrome on low-cost Android phones |
| NFR-12 | Configuration | All values in section 22 editable without a release |

# 24. Screen inventory

| **Area** | **Screens** |
|----|----|
| Public | Home, search results (list and map), property page, lister profile, free check, full check order, lodge a complaint, complaint status, content pages, sign up, sign in, password reset, WhatsApp confirmation page |
| Lister (owner or agent) | Dashboard, my listings, add or edit listing, bulk import, identity verification, leads pipeline, lead detail, deal and payments, customers, payouts (agents), bank account, rate table, performance, site capture |
| Buyer | My enquiries, my full checks and reports, deal payment instructions and proof upload |
| Local official | Registration, dashboard, task detail with five questions and uploads |
| Professional | Dashboard, task detail, accept or decline, report upload, site capture (surveyors) |
| Verifier | Job queue, location check review, full check workspace, task assignment, result and report |
| Marketer | Featured listings, banners, content pages, campaigns, market monitoring panel |
| Management | Management dashboard and queues, identity approvals, partner registration and approval, payments and payouts, rate table, locality lists, complaints desk, WhatsApp outbox, staff accounts, settings, audit log, market monitoring panel, coverage map |

# 25. Data model summary

Main entities and their key relationships. Field lists in modules above are the minimum; the team adds technical fields such as created_at, updated_at and created_by to every table.

| **Entity** | **Holds** | **Linked to** |
|----|----|----|
| User | Email (sign-in, unique), phone (unique), name, password hash, language | Roles, ListerIdentity, BankAccount |
| Role | Buyer, lister, local official, professional, verifier, marketer, director, head of operations | User |
| ListerIdentity | ID number, ID photo, selfie, status, expiry | User |
| BankAccount | Bank, account name, number, branch | User or OwnerContact |
| Locality | Region, district, ward, street or village, approved flag | PropertyRecord, LocalOfficial |
| PropertyRecord | Property ID, pin, boundary, category, size, title type | Listing, VerificationJob, FreeCheck |
| Listing | Lister, kind, selling price, owner's price, rate version, status | PropertyRecord, OwnerContact, Lead |
| OwnerContact | Owner name, WhatsApp, bank account, confirmations | Listing |
| Media | File, source, location, time, device, hash | Listing, Evidence |
| Lead | Buyer, stage, notes | Listing, Deal |
| Deal | Final price, breakdown, payment status, sale agreement | Lead, Payment, Payout |
| Payment | Payer, payee, amount, reference, proof, confirmed by | Deal or VerificationJob |
| Payout | Agent, amount, status, bank reference, proof | Deal |
| RateTable / RateBand | Version, bands, rates, published date | Listing |
| VerificationJob | Type, verifier, status, result, expiry | PropertyRecord, Task, Evidence |
| Task | Kind (consent, site capture, local office, professional, registry), assignee, status | VerificationJob |
| Evidence | Item, answers, files, points, created by, locked | Task |
| LocalOfficial | Name, position, ID, photo, WhatsApp, stamp, status | Locality, Task |
| Professional | Name, type, registration number, coverage, status | Task |
| FreeCheck | Input, verdicts, report file, WhatsApp number | PropertyRecord |
| Confirmation | Token, purpose, content, decision, time, device | Any entity needing consent |
| Complaint | Number, type, status, handler, outcome | Listing, Deal, User |
| Notification | Channel (screen, email, outbox, self-service), message text, status, created by, sent by, sent at | User or phone number |
| Setting | Key, value, changed by | System |
| AuditLog | Actor, action, entity, before and after, time | All |

# 26. Open items that affect development

| **Item** | **Impact** | **Owner** |
|----|----|----|
| Final commission rate table | Seed data for PAY. Build can proceed with example bands | Director |
| Full check fee | Shown before ordering. Build with a configurable value | Director |
| Payment to partners per job | May add a partner payout feature similar to agent payouts | Director |
| Licence for receiving buyer money | May change how Oweru's bank account is described to buyers | Director, legal adviser |
| Get Oweru's WhatsApp number on the WhatsApp Business app and link staff computers | Needed for the outbox before launch. Development can use any test number | Head of Operations |
| Staff to send WhatsApp outbox messages | Decide who sends and during which hours; affects how fast owners and partners are reached | Head of Operations |
| Choose and contract a map and satellite imagery provider | Needed for MAP, VER location checks and FRC. Development continues on OpenStreetMap | Head of Operations |
| Register with TRA for electronic fiscal receipts (EFD or VFD) | Needed for PAY-11 before the first payment. Automatic receipts (PAY-14) follow | Finance, tax adviser |
| Property ID format | Needed before first listing | Head of Operations |
| Guarantee wording | Stays hidden until approved | Director, legal adviser |
| Foreign buyer warning for village land | Possible extra step in full check ordering | Director, legal adviser |
| Email address for every account | Sign-in uses email, so local officials and professionals need an email address when they register. Confirm this works for officials without email, or decide an alternative | Head of Operations |
