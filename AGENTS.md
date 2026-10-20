# AGENTS.md

Instructions for anyone, human or coding agent, changing this repository.

## The project

Oweru Marketplace is a Tanzanian web marketplace for land, houses and commercial property. Every property shows honestly what Oweru has checked, from Level 0 (listed) to Level 3 (Oweru Verified, a paid full check). Owners and independent agents list; buyers search, enquire and pay by bank transfer; local officials and professionals do verification tasks; Oweru staff run desks for checks, payments, complaints, marketing and the market panel.

- `backend/`: Django 5.2 + DRF API at `/api/v1/`, PostgreSQL/PostGIS, Celery + Redis, private S3 storage.
- `frontend/`: React 19 + TypeScript single-page app, Vite, Tailwind v4, i18next (Swahili default).

## Read first

| Document | What it is |
|---|---|
| [docs/srd.md](docs/srd.md) | **The build specification.** Requirement IDs, rules, statuses, acceptance tests. Wins over everything else |
| [docs/prd.md](docs/prd.md) | The business view and the reasons behind the rules |
| [docs/architecture-essentials.md](docs/architecture-essentials.md) | One page: the ten things to know |
| [docs/architecture.md](docs/architecture.md) | How it is built, shared patterns, and what is done per module |
| [docs/design.md](docs/design.md) | Visual system, screen patterns, the process for new screens |

## Commands

Windows, PowerShell. Paths are from the repository root.

Backend (from `backend/`, using the existing virtual environment):

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --settings=config.settings.development
.\.venv\Scripts\python.exe -m pytest                                  # PostgreSQL/PostGIS (config.settings.test_postgresql)
.\.venv\Scripts\python.exe -m pytest apps/complaints -q               # one app
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=config.settings.development
```

Full native setup (PostgreSQL 18 + PostGIS, Memurai, GDAL, Celery): [docs/NON_DOCKER_LOCAL_DEVELOPMENT.md](docs/NON_DOCKER_LOCAL_DEVELOPMENT.md).

Frontend (from `frontend/`):

```powershell
npm run dev -- --port 5173 --strictPort   # port 5173 is fixed: backend URLs and CORS point to it
npx tsc -b                                # type check
npm run lint                              # oxlint
npm run build                             # type check + production build
```

Vite proxies `/api` to `127.0.0.1:8000`, so no CORS setup is needed in development.

## Rules that must never break

These come from the SRD and PRD. Code review rejects changes that break them.

- **Levels are calculated, never set.** Level wording is fixed (SRD 10). The name "Oweru Verified", its gold badge and shield are for Level 3 only.
- **Never use the word "guarantee"** in the interface, messages, PDFs or emails. **Never use "Oweru Agent".**
- **Owner privacy.** The owner's name, contact, price and bank details are never shown to buyers or returned by public endpoints. Confirmation links never reveal the buyer.
- **Verdict, not method.** The free check returns verdicts only: no coordinates, boundaries or methods. Public maps show approximate positions.
- **No SMS. No automatic WhatsApp.** The system prepares WhatsApp messages; a person sends them from the outbox or their own WhatsApp.
- **Money is recorded, not moved.** All payments are bank transfers outside the system.
- **Nothing is deleted.** Property Records, evidence, submissions, deals, payments and audit rows are kept; corrections are new versions.
- **The server enforces every permission.** Hiding a button is UX, never security.
- **Settings, not constants.** Thresholds, expiries, limits and fees come from `setting(key)` (`backend/apps/verification/configuration.py`).
- **Swahili first.** No hard-coded user-facing text. Every string is in both `frontend/src/i18n/sw.ts` and `en.ts`, with the same keys.

## Backend conventions

- Business rules live in `apps/<domain>/services.py`. Views and serializers stay thin.
- Start every protected service with `authorize(actor, "<permission>")` (`apps.leads.policies`), then scope objects to the actor.
- Write `create_audit_log(...)` for every staff or partner action and status change; `record_sensitive_access(...)` for every read of identity, bank, payment or private verification data.
- Money, orders and uploads go through `apps.payments.idempotency.execute(...)` and require an `Idempotency-Key`. Editable records use a `version` and return 409 on conflict.
- Messages: create a domain notice row, let `apps/notifications/signals.py` call `emit(...)`. Text comes from `notifications/catalog.py`, in the recipient's language. Links point to frontend pages via `public_link(...)` and `MARKETPLACE_PUBLIC_URL`, never to `/api/v1/`.
- Uploads are private and content-validated; return signed links, never storage paths.
- Use PostGIS for distance, overlap and area. Keep exact pins out of public serializers.
- Every rule you add gets a test in the app's `tests/`. Name the behaviour (`test_scope_is_frozen_in_both_languages`) and mention the requirement ID in a comment or docstring where it helps.

## Frontend conventions

- Call the API only through `src/lib/*Api.ts`, which use `request()` from `src/lib/api.ts`. Pass `idempotencyKey()` as `Idempotency-Key` on money, orders and uploads.
- New page: route in `src/App.tsx` behind the right guard (`RequireAuth`, `RequirePermission`), sidebar item in `src/layouts/navigation.ts`, strings in both i18n files.
- Follow [docs/design.md](docs/design.md): tokens from `src/index.css`, shared components first, mobile-first at 360 px, gold buttons with navy text.
- Lint rules that often bite: no `setState` synchronously inside an effect body (do it in handlers or async callbacks); a file that exports a component exports only components; no `Date.now()` or random values during render; every list item has a `key`.
- Motion: `motion/react` for component state, GSAP `useGSAP` scoped to a ref for page sequences. Never both on the same element's `transform`. Respect reduced motion.
- `/auth/me/` does not return roles yet; `loadAccess()` infers them. Do not build new security assumptions on it.

## Before saying something is done

1. The SRD requirement and its acceptance test are met, including permissions, audit and the honesty rules above.
2. Backend: tests for the change pass. Compare failures against the same tests without your change (`git stash`) so you only report what you broke.
3. Frontend: `npx tsc -b` and `npm run lint` are clean. The screen works at phone width and in both languages.
4. Docs: update [docs/architecture.md section 10](docs/architecture.md#10-status-by-module) when a module's status changes.

## Git

- Branch from `main`: `feature/<topic>` or `fix/<topic>`.
- Commit messages: `type(scope): summary [REQ-IDS]`, for example `feat(payments): owner receipt confirmation [PAY-08]`. Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.
- Commits and PRs are authored by the developer only. Do not add AI co-author trailers or "generated with" lines.
- Another developer works on the backend in parallel. Before merging: fetch, merge `origin/main` into your branch, resolve conflicts, run the checks, then fast-forward `main` and push both.
- Never commit `backend/.env`, local databases (`*.sqlite3`, `*.bak`), `.playwright-mcp/` or screenshots.

## Writing style

Plain English, short sentences. No em dash in docs, commit messages or interface copy: use a comma, colon, parentheses or a full stop.
