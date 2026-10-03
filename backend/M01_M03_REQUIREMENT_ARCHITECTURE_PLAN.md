# Oweru Marketplace M01-M03 status and next steps

Updated 2 October 2026 against SRD v1.3 and Backend Guide v1.1. This supersedes the initial plan at commit 98999f6, which described missing specifications, phone sign-in and optional email. That historical description is no longer the current architecture.

## M01 foundation

Django environment-specific settings, PostgreSQL/PostGIS configuration, DRF v1 routing, custom UUID users, JWT, Redis/Celery configuration, CORS/security headers, JSON logging, base timestamps, OpenAPI, health endpoints and pytest infrastructure exist. Infrastructure configuration is not evidence that every production service is running.

## M02 accounts

Email is required, unique, normalized and used for sign-in/reset; phone remains required and unique. Password validation/hashing, five-failure/fifteen-minute lockout, JWT refresh, own-profile retrieval, email reset and language preferences exist. Registration now atomically establishes Buyer and its authorization audit event. Persistent public/operational classification enforces SRD section 4.

Full ACC-06 account provisioning, first-sign-in password change, email verification, phone confirmation, profile editing/deletion workflow and support-assisted reset remain unfinished. The pre-existing sixty-minute reset timeout still differs from ACC-03's thirty-minute email rule; it was not changed during the Roles & Permissions milestone.

## M03 roles and audit

The original eight models' role codes and Role/Permission/UserRole/RolePermission architecture are preserved. The catalog has explicit SRD-derived action permissions and default grants. Management has no wildcard bypass. Governed services require active actors, category-compatible targets, explicit Management permissions and atomic audit writes. Self-assignment, public-to-operational promotion, premature partner onboarding and arbitrary matrix editing are denied.

Management API: /api/v1/management/authorization/. Setup uses bootstrap_marketplace_management for existing active operational superusers. Only Verifier/Marketer assignments and non-Management operational revocations are exposed. Optional role-wide outbox.send grants for Verifier/Marketer can be toggled under Management control; this is the sole runtime matrix exception explicitly supported by the SRD.

See [the complete authorization contract](doc/BACKEND_AUTHORIZATION.md) for catalog, matrix, APIs, audit, migrations, tests and requirement traceability.

## Migration and verification boundary

Existing migrations are unchanged. New forward migrations add and classify account_category, reject mixed historical categories, and seed a frozen permission catalog/default matrix with system audit events. Unknown existing grants require review instead of silent replacement. Historical roleless public accounts are not assigned guessed roles.

Default tests use in-memory SQLite. PostgreSQL test settings and raw audit-trigger tests are available, but local execution requires valid PostgreSQL credentials and test-database creation privileges. SQLite passes do not establish PostgreSQL row-lock behavior or trigger execution.

## Next milestones

Proceed to M04 Localities, then identity and property/listing modules. Add domain services, queryset/field filtering, object policies and acceptance tests alongside their actual models. Permission codes do not implement these workflows.

Resolve the documented bank-access, anonymous-complaint and management-title contradictions before those domains. Keep all work within Oweru Marketplace; no PA System assumptions or permissions apply.
