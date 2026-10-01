# Oweru Marketplace M01–M03 Plan

## Source and repository findings

- The active checkout contained no tracked source files at the start of this work.
- `D:\my codes\Oweru_Marketplace-main.zip` contains a separate, much larger Marketplace snapshot with Django backend and frontend code. Its backend already includes M04+ domain areas; it is being used only to understand the intended product context, not copied into this M01–M03 foundation.
- The requested **Oweru Marketplace SRD v1.2** and **Oweru Marketplace Backend Development Master Guide** were not present in the checkout, sibling project archive, or searched `D:\my codes` tree. Business traceability therefore uses the detailed requirements provided in the task; document-section citations cannot be made until those files are supplied.
- The archived backend currently configures Django 5.2, a phone-based identity app, parties/roles, audit, and later marketplace apps. It uses environment-backed settings in part, but has a development secret fallback and SQLite fallback. Existing functionality must not be assumed to be part of the empty active checkout.

## M01–M03 architecture

### M01 — Foundation

- Django project `config` with base/development/production/test settings.
- PostGIS PostgreSQL as the application database; production requires explicit environment configuration. SQLite is reserved for unit/API test settings only.
- Custom phone-based `accounts.User` is installed before the first migration.
- DRF API rooted at `/api/v1/`, URL-path API versioning, SimpleJWT, schema/docs, CORS, cache/Redis, Celery, security headers, JSON logging, common timestamp base, health/readiness endpoints, pytest configuration.
- No M04+ property, listing, enquiry, verification, deal, payment, or payout models/tasks.

### M02 — Accounts and authentication

- User fields: phone, full name, optional email, `en`/`sw` preference, active/staff/superuser lifecycle, failed-login counter and lock expiry.
- Registration hashes passwords and relies on a database unique constraint for phone identity.
- Phone/password login issues JWTs. Five consecutive failures lock a known account for 15 minutes; IP-based DRF throttling also limits anonymous auth requests.
- Email reset is token-based and does not reveal whether an account/email exists. Accounts without email receive a support-assisted WhatsApp direction; no automated WhatsApp reset is created.
- Sensitive confirmation foundation stores only a hash of a random confirmation token, purpose, subject reference, expiry, and consumption timestamp. It does not implement future workflows.
- `account_type` is not added as an ambiguous duplicate of the explicit role system; confirm its intended meaning against the SRD before introducing it.

### M03 — Roles, permissions, and audit

- Database-backed `Role`, `Permission`, role-permission and user-role relationships; only the eight roles listed in the task are seeded.
- Reusable DRF permission classes check assigned role or permission codes; self-only account access is enforced by the current-user endpoint. No future marketplace object policies are fabricated before those objects exist.
- Append-only audit events capture actor, action, entity reference, before/after JSON, IP, user agent, and timestamp. No public mutation API is provided; admin access is read-only. Sensitive access can use the same audit service.

## Sequencing and verification

1. Implement M01 models/settings/routing, generate the initial custom-user migration, and run checks plus foundation tests.
2. Implement M02 auth services/serializers/endpoints and test registration, lockout, JWT, reset, and data exposure.
3. Implement M03 role/permission and audit services/permissions and test enforcement and immutability.
4. Run all tests and requirement traceability. PostgreSQL/PostGIS/Redis acceptance checks are reported separately if those services are unavailable locally; SQLite tests do not prove PostGIS readiness.

## Requirements requiring source-document confirmation

- The exact public API route naming/response contract from the missing architecture guide.
- Whether `account_type` has a distinct SRD meaning apart from roles.
- Any constraints on phone normalization, reset-link lifetime/host, or confirmation token lifetime beyond the requirements in the task.
- Whether specific audit data retention or sensitive-field redaction rules are defined in SRD v1.2.
