# Marketplace authorization foundation

M03 backend authorization foundation, based on SRD v1.3 and Backend Guide v1.1. Future-domain permissions are action contracts, not implemented domain workflows.

## Architecture and governance

The existing Role, Permission, UserRole and RolePermission models remain authoritative. Django groups and Django superuser privileges are separate: neither implies Marketplace access. Management receives explicit database grants, not a wildcard bypass.

Public roles: buyer, owner, agent. Partner roles: local_official, professional. Staff roles: verifier, marketer, management. Partners and staff share the operational account category; the SRD does not unambiguously forbid combining staff and partner roles. Public and operational accounts cannot mix, including revoked assignment history. Persistent account_category prevents revoke-then-promote category laundering. Effective checks refuse inconsistent assignments. Direct ORM/database access remains a trusted deployment capability, not a supported user mutation path.

Public registration assigns Buyer atomically with its audit event (sections 2.2/4, ACC-01). Client-supplied role/category/staff flags are not writable registration fields. Existing roleless public accounts remain roleless: migration does not guess their onboarding history. Owner/Agent acquisition waits for listing/lister onboarding (IDV-02, LST-04); a role must never substitute for identity/phone verification. There is no generic self-service role endpoint.

Management may assign Verifier or Marketer to an existing active operational account. Such accounts must come from trusted provisioning with account_category='operational'; full account creation/first-password-change workflows in ACC-06 remain deferred. Public registration cannot create these targets. Partner assignment/reactivation is blocked pending actual invitation/approval workflows. Management can revoke Verifier, Marketer, Professional and Local Official assignments, including on inactive accounts or inactive roles. Revocation removes role access, not login itself; partner login deactivation remains part of ACC-06/LOC-06.

Management assignment/revocation is not exposed over HTTP. A trusted setup command assigns Management to an existing active operational Django superuser, recording that account as the setup actor. It is idempotent. Django superusers have no bypass in normal authorization services:

```powershell
python manage.py createsuperuser
python manage.py bootstrap_marketplace_management --user-id <uuid>
```

These are trusted deployment operations. Further Management appointments also require this setup path. Use separate public accounts for Marketplace participation.

## Fixed policy and optional grants

The canonical matrix is fixed policy. The only runtime grant/revoke supported is outbox.send for Verifier or Marketer, justified by section 4 (If granted), NTF-02 and section 26. It applies to every holder of the selected role, not an individual override. Both roles start without it. Management requires authorization.manage_outbox to change it. No arbitrary permission creation/deletion or matrix-editing API exists. The old permission_name service argument remains accepted for compatibility but cannot change catalog metadata.

## Permission catalog and matrix

The complete catalog and role matrix follow below. Every grant is an action gate. Ownership, assignment, locality, active-deal participation, consent, conflicts of interest, record state and field visibility require separate future domain policies. HasMarketplacePermission does not grant access to every object.

## Management API

Prefix: /api/v1/management/authorization/

| Method and relative path | Required permission | Behavior |
|---|---|---|
| GET roles/ | authorization.view | Eight roles, code/name/active state |
| GET permissions/ | authorization.view | Permission code/name/source metadata |
| GET roles/{role_code}/permissions/ | authorization.view | Current role grants |
| GET users/?email={email} | authorization.view | Exact (case-insensitive) email match only; returns id, full_name, account_category, is_active. No partial search or listing. 400 without email |
| GET users/{user_id}/roles/ | authorization.view | Role codes and assignment active flags only |
| POST users/{user_id}/roles/assign/ | authorization.assign_role | Body: role_code; Verifier/Marketer only; 200, including idempotent calls |
| POST users/{user_id}/roles/revoke/ | authorization.revoke_role | Body: role_code; non-Management operational roles; 204, including no-op |
| PUT roles/{role_code}/outbox-send/ | authorization.manage_outbox | Body: enabled boolean; Verifier/Marketer only; 200 |

All require JWT, an active Management assignment, and the explicit permission. No Django session fallback. Anonymous returns 401; authenticated unauthorized returns 403; validation failures return 400; missing target resources return 404. No passwords, tokens, contacts, login counters, identity information or audit snapshots appear in responses. Serializers call the services; views do not implement governance rules.

## Own access in the profile

GET /api/v1/auth/me/ (and the user object returned by registration and login) includes account_category, roles and permissions. They list only effective access, computed by the same rules as has_role and has_marketplace_permission: inactive accounts, inactive roles or assignments, and category-inconsistent assignments are excluded. The frontend uses them to choose which screens to show; the API still enforces every permission on each request.

## Services and transactions

assign_role/revoke_role validate a freshly fetched actor, explicit Management permissions, target category, permitted role and self-mutation restrictions. Active accounts/roles are required for assignment. Revocation deliberately works for inactive targets/roles so access can still be removed. Duplicate requests are no-ops without duplicate events. Revoked staff roles can be reactivated through the same governed service.

grant_permission/revoke_permission require active Management and authorization.manage_outbox; unknown codes and changes outside the optional-grant allowlist are refused. User rows are locked in UUID order; optional grant mutations also lock the role. PostgreSQL row-lock behavior still needs integration execution.

Each mutation and its audit write share transaction.atomic(). Audit failure rolls back assignment, reactivation, revocation or grant deletion/creation. Registration also rolls back the new user if its required Buyer audit fails.

Events: role.assigned, role.revoked, permission.granted, permission.revoked. They contain actor, entity reference, target user where relevant, role/permission codes, explicit before/after active/granted state, timestamp, and request IP/user agent. No-op calls emit no change event. Migration seed events use a null system actor and an explicit migration source; setup events use the target superuser as actor. Sensitive-access logging remains an explicit domain integration helper.

Audit records retain model/queryset immutability and the existing PostgreSQL update/delete rejection trigger. Authorization and audit admin are read-only even for superusers; viewing additionally requires Marketplace Management and the respective authorization.view/audit.view grant, as well as Django admin permissions.

## Reusable DRF classes

- HasMarketplaceRole: requires a configured required_role, an authenticated active user, active role and active assignment with a compatible persisted account category.
- HasMarketplacePermission: same effective-role checks plus required_marketplace_permission and a current database grant. Missing configuration denies access.
- IsManagement: checks the management role without mutating view configuration. Management APIs additionally require an explicit permission.
- IsSelf: requires an authenticated active persisted account and matches user_id, falling back to id. Missing ownership and another user are denied. It is not a substitute for listing/task/payment scope.

## Forward migrations and deployment

- accounts.0003_account_category adds the category field and user_category_valid check. Historical operational roles or Django staff/superuser flags classify accounts as operational; other accounts remain public. Mixed public/operational history causes a preflight error requiring deliberate operator review, not silent revocation.
- authorization.0002_permission_catalog uses a frozen policy snapshot and historical models on the migration connection. It installs permissions and grants with get_or_create, audits new grants, preserves optional grants, and rejects existing noncanonical grants for operator review. Repeated seeding does not duplicate rows or events. It is intentionally irreversible: rolling it back must not silently remove policy or immutable audit history.
- Existing migrations are unchanged. Existing unique user-role/role-permission constraints and userrole_active_idx remain. No extra index is necessary for the current foreign-key lookups.
- Future policy changes need a new reviewed migration; never edit this seed or import mutable runtime catalog data from it. The seed is additive/idempotent, not a runtime policy-reconciliation job.

## Verification

```powershell
python manage.py check --settings=config.settings.test
python manage.py makemigrations --check --dry-run --settings=config.settings.test
python -B -m pytest -p no:cacheprovider
python -B -m pytest -p no:cacheprovider --ds=config.settings.test_postgresql
```

The PostgreSQL variant uses POSTGRES_* / DATABASE_URL and a separate Django test database; the account needs test-database creation privileges. Never point test settings at a production database. Raw SQL audit-trigger tests run only on PostgreSQL. Default SQLite tests cover service atomicity, constraints/indexes, migration graph, seed idempotency, category preflight, JWT management APIs, effective access and privilege-escalation denial.

Local PostgreSQL execution was blocked: the server was reachable but authentication reported no password supplied. Docker Desktop's engine pipe was also unavailable. No PostgreSQL test success, row-lock behavior, trigger execution, PostGIS readiness or production database migration is claimed.

Validated on 2 October 2026: 36 original cases retained, 86 added cases, 122 collected; **120 passed, 2 skipped in 2.39s**. Both skips are PostgreSQL-only raw SQL trigger cases. The original authorization assertions remain; their setup now supplies an authorized actor or trusted bootstrap instead of relying on the removed actorless assignment behavior. The foundation database assertion still requires SQLite by default and recognizes the explicitly selected PostgreSQL test settings. Django check: no issues. Migration drift check: no changes detected. Git whitespace check passed; frontend, source specifications and historical migrations remain unchanged.

## SRD traceability

| Requirement | Permission / role | Service or API | Tests |
|---|---|---|---|
| Sections 2.2/4; ACC-01 | Buyer/default public category | register_public_user, existing registration API | test_registration_only_assigns_buyer_and_audits; test_registration_audit_failure_rolls_back_user |
| Section 4 separation | Public versus operational role sets | _category; effective-role query; category migration | test_public_category_cannot_be_promoted_even_without_roles; test_revoked_public_history_cannot_be_bypassed; test_inconsistent_category_assignment_never_grants_access; category backfill tests |
| Section 4; ACC-06 (authorization portion) | authorization.view/assign_role/revoke_role; Management | role read/assign/revoke APIs and services | test_management_mutation_api; test_management_read_api_access; test_management_needs_explicit_grant; test_management_cannot_bypass_deferred_onboarding |
| Section 2.2 setup | Management | bootstrap_marketplace_management | test_bootstrap_command_idempotent_and_restricted; test_bootstrap_audit_failure_rolls_back; test_superuser_is_not_marketplace_management |
| Section 4; NTF-02; section 26 | outbox.send; optional Verifier/Marketer; authorization.manage_outbox Management | grant_permission/revoke_permission; outbox-send endpoint | test_optional_permission_grant_revoke_and_audit; test_outbox_api_is_narrow; test_canonical_matrix_cannot_be_changed |
| Section 4; NFR-03 | All action permissions | permission classes and User effective-role methods | original role/permission tests; test_effective_permission_stops_immediately; test_permission_classes_fail_closed; test_stale_user_object_does_not_retain_access |
| ADM-05 (authorization changes) | Audit event stream | atomic authorization services; read-only admin | test_audit_failure_rolls_back_mutation; test_assign_revoke_reactivate_idempotency_and_audit; test_admin_has_no_mutation_bypass; existing audit tests |
| Section 4 and catalog source IDs | Exact default grants for all eight roles | frozen seed migration | test_catalog_and_frozen_seed_match; test_seed_is_idempotent_and_preserves_optional_grant; test_seed_refuses_noncanonical_existing_grants |

The catalog's source column traces every future-domain permission individually. Those entries are tested as seeded policy, not as completed future business workflows.

## Unresolved SRD conflicts and deferred policies

- Section 4 agent bank access conflicts with PAY-05. No bank permission is defined or granted pending resolution.
- Section 4 complaint role table versus CMP-01 anonymous complaints remains unresolved. No complaint submission permission or complaint endpoint is introduced. complaint.handle is an action placeholder only; complaint object scope and final review are deferred.
- Section 25 role terminology differs from section 4/guide. Existing eight roles remain; no Director/Head of Operations role codes are introduced.
- Director-specific final review and Head of Operations approval responsibilities coexist with identical Management permissions. Do not use the shared Management role to silently resolve those future workflow distinctions.
- Anonymous public search/free checks and complaint access require dedicated future endpoint policy; catalog entries do not mandate authentication for otherwise public resources.
- Listing ownership, buyer participation, exact locality, professional coverage/type, assignments, consent, conflict of interest, adverse-report recipients, sensitive field filtering, and submitted-evidence immutability wait for their domain models.
- Implemented after this milestone (see backend/README.md, accounts.account_services): ACC-06 staff account creation with temporary passwords and forced change, edit, deactivate/reactivate; ACC-05 email confirmation; ACC-03 30-minute reset links; ACC-08 profile edit and deletion requests; logout token revocation; the phone confirmation link and page (SRD 20.3). Still deferred: partner (local official/professional) onboarding, support-assisted outbox resets (24-hour links), identity submission (M05) and the WhatsApp outbox (M21) that will send phone confirmation links.

This foundation supports M04+ development after migrations and deployment validation. It does not certify future domain policies or production readiness.

## Complete permission catalog

| Code | Meaning | SRD source |
|---|---|---|
| account.view | View own profile | ACC-08 |
| account.update | Edit own profile | ACC-08 |
| account.request_deletion | Request own account deletion | ACC-08 |
| account.manage | Manage staff and partner accounts | ACC-06; section 4 |
| account.suspend | Suspend or restore accounts with a reason | ADM-02 |
| authorization.view | Inspect roles and grants for account administration | ACC-06; section 4 |
| authorization.assign_role | Assign permitted staff roles | ACC-06; section 2.2 |
| authorization.revoke_role | Revoke operational roles | ACC-06 |
| authorization.manage_outbox | Configure optional staff outbox-send grants | section 4; NTF-02; section 26 |
| identity.submit | Submit own lister identity | IDV-01 |
| identity.review | Approve or reject lister identities | IDV-03 |
| property.search | Search public properties; anonymous policy is separate | SRC-01; section 4 |
| listing.view | View public listings; anonymous policy is separate | SRC-03; section 4 |
| listing.create | Create listings within permitted scope | LST-02; section 4 |
| listing.update | Edit own listings; management scope requires domain policy | section 4; LST-10 |
| listing.import | Import own listings or on a lister's behalf | LST-11 |
| listing.view_owner_price | View owner price within own listing or management scope | section 4 |
| listing.suspend | Suspend or restore listing with reason | ADM-02 |
| lead.create | Enquire about a listing | section 4; LEAD-01 |
| lead.view | View own leads; management may view all | section 4; LEAD-06 |
| lead.update | Manage own lead stages and notes | section 4; LEAD-02 |
| deal.view | View own deals; management may view all | section 4 |
| deal.update | Manage own deal closing | section 4; LEAD-03 |
| verification.order | Order a full check | FUL-01; section 4 |
| verification.complete_task | Complete tasks subject to assignment/locality/conflict checks | section 4; VER-06; LOC-02; PRO-02 |
| verification.record_result | Record verification results | section 4; FUL-07 |
| verification.assign_task | Assign professional verification tasks | FUL-05; PRO-02 |
| partner.manage | Register and approve partners through onboarding | section 4; LOC-01; PRO-01 |
| commission.view | View current commission table | PAY-02; PAY-01 |
| commission.manage | Publish commission rate table versions | PAY-01 |
| payment.submit_proof | Submit own deal/full-check payment proof | PAY-07; PAY-13 |
| payment.confirm | Confirm Oweru receipt | PAY-09; PAY-13 |
| payout.record | Record agent payout | PAY-10 |
| payout.hold | Hold payout with a reason | PAY-12 |
| complaint.handle | Handle verification complaints or management scope; object policy deferred | section 4; CMP-04 |
| outbox.send | Manually send and mark outbox messages sent | section 4; NTF-02 |
| marketing.manage | Manage featured listings, banners and bilingual content | MAR-01; MAR-02; section 4 |
| marketing.send_campaign | Send campaigns only to consenting recipients | MAR-03; section 4 |
| analytics.view | View non-personal market monitoring data | MON-01; MON-03; section 4 |
| analytics.export | Export market monitoring views | MON-02 |
| settings.manage | Edit database settings with change log | ADM-04 |
| audit.view | View immutable management audit log | ADM-05; section 24 |

## Complete default role grants

| Role | Permissions |
|---|---|
| buyer | account.view, account.update, account.request_deletion, property.search, listing.view, lead.create, verification.order, payment.submit_proof |
| owner | account.view, account.update, account.request_deletion, identity.submit, property.search, listing.view, listing.create, listing.update, listing.import, listing.view_owner_price, lead.create, lead.view, lead.update, deal.view, deal.update, commission.view |
| agent | account.view, account.update, account.request_deletion, identity.submit, property.search, listing.view, listing.create, listing.update, listing.import, listing.view_owner_price, lead.create, lead.view, lead.update, deal.view, deal.update, commission.view |
| local_official | account.view, account.update, account.request_deletion, verification.complete_task |
| professional | account.view, account.update, account.request_deletion, verification.complete_task |
| verifier | account.view, account.update, account.request_deletion, verification.complete_task, verification.record_result, verification.assign_task, complaint.handle |
| marketer | account.view, account.update, account.request_deletion, marketing.manage, marketing.send_campaign, analytics.view, analytics.export |
| management | account.view, account.update, account.request_deletion, account.manage, account.suspend, authorization.view, authorization.assign_role, authorization.revoke_role, authorization.manage_outbox, identity.review, property.search, listing.view, listing.create, listing.update, listing.import, listing.view_owner_price, listing.suspend, lead.create, lead.view, deal.view, verification.record_result, partner.manage, commission.view, commission.manage, payment.confirm, payout.record, payout.hold, complaint.handle, outbox.send, marketing.manage, marketing.send_campaign, analytics.view, analytics.export, settings.manage, audit.view |
