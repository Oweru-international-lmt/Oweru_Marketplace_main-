# M19 through M22 requirements and implementation plan

Investigation resumed 9 October 2026. Backend only, Oweru Marketplace. Baseline is clean `main` at `a42aa1e`; no commit or push is authorized.

## Authority

Business rules: `docs/backend_authorization/Oweru-Marketplace-SRD-v1.3.docx` (2 October 2026), sections 4, 16, 17, 20–23 and 26. Engineering guide: `Oweru_Marketplace_Backend_Development_Guide-v1.1.docx`, phases 23–26, sections 39–45 and roadmap M19–M22. SRD takes precedence. Historical reports reviewed: `M14_M18_AUDIT_AND_DEPENDENCIES.md` and `M17_M18_IMPLEMENTATION_AND_VALIDATION.md`. No separate M14–M16 implementation reports were found by milestone filename search.

## Exact milestone requirements

### M19 Free public check

| ID | SRD requirement |
|---|---|
| FRC-01 | Input: map pin, stated description (size, category, claims such as "beachfront"), optional photos, optional link to an outside listing, and the user's WhatsApp number. |
| FRC-02 | Automatic verdicts: location exists on land in Tanzania; duplicates found on Oweru records; photo location mismatch; gross location mismatch with the description. |
| FRC-03 | Show the verdict on screen with a Download PDF button, and a "Send to my WhatsApp" button that opens the user's own WhatsApp with the report link ready to send to themselves. Email a copy if an address is given. The link works for 30 days (configurable). |
| FRC-04 | The report contains a reference number, date, details as entered, each verdict in plain words, the statement "This is not ownership verification" and how to order the full check. It never contains coordinates, boundaries or the method. |
| FRC-05 | Save each submission as an outside Property Record and register the user as a lead for Oweru. |
| FRC-06 | Limit 5 checks per WhatsApp number per day (configurable). |

Free Check cannot grant Level 3. Anonymous users are eligible. Expiring bearer report access is necessary for anonymous self-service sharing; it must expose only a sanitized report, never canonical geometry or private Full Check evidence.

### M20 Complaints desk

| ID | SRD requirement |
|---|---|
| CMP-01 | Without sign-in: name, WhatsApp number, role, type, related property or deal, description, evidence files; relevant page context can pre-fill references. |
| CMP-02 | Staff log WhatsApp/email complaints into the same desk. |
| CMP-03 | Immediate on-screen number; WhatsApp/email acknowledgement by the same channel within 1 working day. |
| CMP-04 | Fake/wrong listing and other route to Head of Operations; conduct, payment/payout and privacy to management; verification result to verifier first, then management. |
| CMP-05 | Received, In review, Waiting for information, Resolved, Under final review, Closed; complainant sees status through WhatsApp link. |
| CMP-06 | An open deal complaint automatically holds agent payout. |
| CMP-07 | Record/send outcome and reasons; Director final review request within 14 days. |
| CMP-08 | Payment/payout resolution target 5 working days, others 10; highlight overdue to management. |

Transition design must preserve immutable communications and reasons, constrain assigned verifier visibility to verification complaints, and keep complainant status capability separate from staff evidence. The SRD lists states but does not enumerate every allowed edge; documented service edges implement the stated lifecycle. Resolution does not silently authorize financial payout release.

### M21 Notifications

NTF-01: single layer with screen, email, staff WhatsApp outbox and self-service; use section 20.4 catalogue channels. NTF-02: authorized staff outbox, manual send/mark-sent, waiting highlight, sent history. NTF-03: self-service prefilled click-to-chat. NTF-04: database-editable Swahili/English texts. NTF-05: no SMS and no automatic WhatsApp. NTF-06: log email success/failure and outbox creation/sending. NTF-07 (Should): future provider switch without changing domains.

Catalogue: phone confirmation (outbox); password reset (email or support outbox); identity decision (screen/email); owner price/bank confirmation (outbox); new lead (screen/email); contact lister (self-service); closing payment instructions (screen/email, lister self-service); owner payment receipt (external-owner outbox or owner screen); payout paid (screen/email); Full Check consent (external-owner outbox or owner screen); Full Check report ready (screen/email); official registration (outbox); verification task assigned (outbox/screen); professional setup (outbox); Free Check report (screen/self-service, optional email per FRC-03); complaint number (screen, WhatsApp outbox for WhatsApp source, email per CMP-03); complaint update/outcome (outbox/email); verification expiry warning (screen/email).

Section 20.2 records recipient name/number, purpose, full localized message/link, creator, sender and time. Default highlight is 2 working hours. Section 20.3 requires random single-use confirmations, 7-day configurable expiry, outbox-only external-owner/partner links, exact decision context and recipient/IP/browser audit. Existing purpose-specific expiry rules must remain intact.

### M22 Management

ADM-01: queues for identities, flagged listings, duplicates, partner approvals, Needs official tasks, payment confirmations, payouts due, complaints by status. ADM-02: suspend/restore listings/accounts with reason. ADM-03: approved streets/villages. ADM-04: every section 22 setting editable with change log. ADM-05: immutable staff/partner audit.

Section 22 defaults: total commission 10%; versioned example commission bands; payout 3 working days; identity 12 months; location 6 months; Full Check 30 days/6 months; consent 7 days; owner contact 3 working days; local-office task 14 days; official registration 14 days; professional task 7 days; confirmation 7 days; outbox highlight 2 working hours; Free Check 5/day and report 30 days; duplicates 50m/10%; corners 10m; photo flags 200m/30 days; area flag 10%; public rounding about 200m; lost/sold review 6 months; complaint acknowledgement 1 working day and resolution 5/10 working days; final review 14 days; Full Check fee Director-approved, unset until configured.

## Architecture findings and reuse

M18 already has VerificationSetting, VerificationNotice, normalized jobs/tasks/results, immutable report versions, private ReportLab PDFs, private media storage, atomic services and ordered locks. Existing generic confirmations and financial notices have separate outboxes; consolidate through compatibility integration rather than replacing tokens. Existing PayoutBlock is explicitly reserved for M20 integration. Existing Lead requires a listing/lister, so anonymous outside-check prospects require a separate lead subtype or a controlled schema extension; do not create a fictional listing/account. PropertyRecord currently requires creator and exact locality; anonymous pin-only submissions need a controlled outside-record extension. Canonical roles include a combined Management role, not Director/Head of Operations distinction. This governance distinction must be explicit before role-specific complaint decisions are enabled; a generic Management permission cannot stand in for Director final review.

Reuse persisted active action permissions plus object policy, existing audit service, private_write_scope cleanup and PostGIS distances. Never expose storage keys. Use forward migrations only. Prior reports document unavailable satellite provider/public datasets and weekday-only deadline limitations. A rectangular Tanzania extent is not proof of land or national jurisdiction; unavailable authoritative geodata must produce an explicit unavailable verdict.

## Acceptance and sequence

Verified pre-implementation baseline: **1,499 passed in 198.42 seconds**, PostgreSQL/PostGIS, no failed/skipped tests. `manage.py check`: zero issues. Migration drift: no changes detected. Docker Engine was available but had zero images/containers; recreated isolated `oweru-m19-tests` network, `oweru-m19-test-db` (PostGIS 16/3.5), and `oweru-m19-test-runner` (Python 3.12). Database has no published port and uses test-only trust authentication within the isolated network. No production data was accessed.

No dedicated Given/When/Then table accompanies SRD sections 16/17/20/21. Tests must derive acceptance directly from the requirement rows above, retaining IDs in documentation.

1. Recreate missing isolated Docker test infrastructure, verify 1,499-test baseline, system check and migration drift before application changes.
2. M19: outside anonymous submission/lead, normalized-phone daily quota under concurrency, provider-neutral verdicts, frozen sanitized bilingual PDF/history and expiring downloads. Test quota races, privacy, invalid input, expiry, report authorization and Level 3 isolation.
3. M20: anonymous complaint/evidence/status capability, staff intake, routing/governance, transitions/history/responses, deadline checks and atomic payout blocks. Test unrelated-object visibility, verifier scope, final review, invalid transitions, multiple holds and concurrency.
4. M21: reuse/import existing durable intents into central notifications; localized editable templates, screen inbox, retryable email adapter and idempotent worker, manual outbox/history/optional grants. Test rollback, duplicate delivery claims, failures/retries and no automatic WhatsApp.
5. M22: management queues, settings validation/history/version protection and existing administration service reuse. Test current persisted privilege, revocation, stale writes, reason enforcement and audit rollback.
6. After each milestone run focused PostgreSQL/PostGIS tests and resolve failures. Finally run complete suite, check/drift/diff checks and inventory backend/docs changes.

## Unresolved deployment policy and integrations

Authoritative Tanzania land/coastline/description datasets and licensed imagery are absent; production conclusions cannot be fabricated. Working-hour calendars, holiday coverage, staff sending schedule, guarantee wording, production Full Check fee and official WhatsApp number need business configuration. Live SMTP, private storage, map and WhatsApp operations must be distinguished from tested adapters. Backend-only scope excludes buttons/screens and M23/M24 analytics/marketing. Report actual coverage and limitations rather than claim launch completeness.
