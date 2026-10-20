# Architecture essentials

The ten things to know before changing anything in Oweru Marketplace. The full picture is in [architecture.md](architecture.md).

1. **Two parts, one contract.** A React 19 single-page app (`frontend/`) and a Django REST API (`backend/`, `/api/v1/`). The API is the only source of truth and the only security boundary. The UI hides what a user cannot use; the API refuses it.

2. **The SRD decides.** [srd.md](srd.md) v1.3 is the build specification. Every rule, status, threshold and screen traces to a requirement ID (`LST-05`, `PAY-08`). Where the PRD differs, the SRD wins. Never invent a business rule: if the SRD is silent, make it configurable and ask.

3. **The Property Record is the centre.** Every listing, free check, full check and duplicate hangs off one permanent `PropertyRecord` with a Property ID. Records, evidence, payments and audit rows are never deleted; corrections are new versions.

4. **Business rules live in services.** `apps/<domain>/services.py` checks permissions with `authorize(actor, "<permission>")`, scopes objects to the actor, writes `create_audit_log(...)`, and logs sensitive reads with `record_sensitive_access(...)`. Views and serializers stay thin.

5. **Retries must be safe.** Money, orders and uploads need an `Idempotency-Key` header (`idempotencyKey()` in the frontend). Edits send the record's `version`; 409 means reload and try again.

6. **Settings, not constants.** Thresholds, expiries, limits and fees come from `setting(key)` in `apps/verification/configuration.py`, editable by management with history. Never hard-code them on either side.

7. **People send WhatsApp, the system prepares it.** No SMS. No automatic WhatsApp. Domain apps create notice rows; `notifications` turns them into screen, email, staff outbox or self-service messages in the recipient's language. Links in messages go to frontend pages built from `MARKETPLACE_PUBLIC_URL`, never to `/api/v1/`.

8. **Honesty rules are code rules.** The level is calculated, never set. Level wording is fixed (SRD 10). "Oweru Verified" style is reserved for Level 3. No "guarantee". No "Oweru Agent". Owner name, contact, price and bank are never shown to buyers. The free check returns verdicts, never coordinates or methods. Public maps are approximate.

9. **Swahili first.** Every visible string comes from `frontend/src/i18n/sw.ts` and `en.ts` (same keys in both). Messages, PDFs and emails are bilingual too.

10. **Built for a cheap phone on 3G.** Mobile-first layouts, compressed lazy images, forms that keep unsent input, and nothing that needs a fast connection to be usable. Design rules are in [design.md](design.md).

## Where things are

| I need to... | Look at |
|---|---|
| Find the rule for a feature | [srd.md](srd.md), search the requirement ID |
| See which endpoints exist | `/api/v1/docs/` (Swagger) or `backend/config/api_urls.py` |
| Know what is built and what is missing | [architecture.md, section 10](architecture.md#10-status-by-module) |
| Call the API from a page | `frontend/src/lib/*Api.ts` via `request()` in `lib/api.ts` |
| Add a page | Route in `frontend/src/App.tsx`, sidebar item in `layouts/navigation.ts`, strings in both i18n files |
| Add a message | `backend/apps/notifications/catalog.py`, a notice row, a signal in `notifications/signals.py` |
| Change a setting's default | `backend/apps/verification/configuration.py` |
| Run things locally | [AGENTS.md](../AGENTS.md#commands) |
