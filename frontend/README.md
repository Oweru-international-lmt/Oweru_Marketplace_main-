# Oweru Marketplace frontend

React web app for the Oweru Marketplace backend in [`../backend/`](../backend/README.md). It covers the public marketplace (home, search and property pages), the accounts module (M02): sign up, sign in, forgot password, reset password and the account page; and the Management screens for roles and staff (M03).

## Stack

- React 19 + TypeScript, built with Vite
- Tailwind CSS v4 (brand tokens in `src/index.css`)
- Motion (`motion/react`) for component and page transitions
- GSAP with `@gsap/react` (`useGSAP`) for headline and reveal timelines
- React Router, i18next (Swahili default, English)

## Run locally

1. Start the Django API on `http://127.0.0.1:8000` (see [`backend/README.md`](../backend/README.md)).
2. In this folder:

   ```bash
   npm install
   npm run dev
   ```

3. Open http://localhost:5173. Vite proxies `/api` to the Django server, so no CORS setup is needed in development.

Port 5173 is fixed on purpose: the backend's `CORS_ALLOWED_ORIGINS`, `PASSWORD_RESET_URL` and `EMAIL_VERIFICATION_URL` point to it.

Other scripts: `npm run build` (type-check and production build), `npm run lint` (oxlint), `npm run preview`.

## Configuration

Copy `.env.example` to `.env.local` to override:

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `/api/v1` | API base URL |
| `VITE_SUPPORT_WHATSAPP` | `255711890764` | Oweru support number for click-to-chat links |

## Screens and endpoints

| Route | Screen | Endpoint |
|---|---|---|
| `/` | Public home: hero, the four verification levels, recently listed property, how buying works | `GET /public/listings/?sort=NEWEST&page_size=6` |
| `/listings` | Search (SRC-01): location bar, filter pills (type, price, size, title type, minimum level), sort, pagination; filters live in the URL | `GET /public/listings/`, `GET /localities/regions/`, `…/districts/?region=`, `…/wards/?district=` |
| `/listings/:id` | Property page (SRC-03): gallery, facts, verification panel with the SRD section 10 wording, lister, WhatsApp contact, enquiry and viewing request | `GET /public/listings/{id}/`, `GET /notifications/self-service/listings/{id}/`, `POST /leads/` |
| `/register` | Sign up with name, email, phone and password; language comes from the header switch | `POST /auth/register/`, then `POST /auth/login/` |
| `/login` | Sign in with email and password | `POST /auth/login/` |
| `/forgot-password` | Request a reset link by email, WhatsApp help for people who can't reach their inbox | `POST /auth/password/reset/` |
| `/reset-password?uid=&token=` | Set new password from the emailed link | `POST /auth/password/reset/confirm/` |
| `/account` | Profile (edit name and language), staff roles, email confirmation status with resend, password change (signs out everywhere), deletion request | `GET /auth/me/`, `PATCH /users/me/`, `POST /auth/email/resend/`, `POST /auth/password/change/`, `POST /users/me/deletion-request/` |
| `/verify-email?token=` | Opened from the confirmation email (ACC-05); path set by the backend's `EMAIL_VERIFICATION_URL` | `POST /auth/email/verify/` |
| `/management/roles` | Roles × permissions matrix; WhatsApp outbox switches for Verifier and Marketer | `GET /management/authorization/roles/…/permissions/`, `PUT …/roles/{role}/outbox-send/` |
| `/management/staff` | Create a Verifier or Marketer account (the backend emails a set-password link); find an account by email; give or remove Verifier and Marketer roles; rename, deactivate or reactivate with a reason | `…/users/?email=`, `…/users/{id}/roles/…`, `POST /management/accounts/`, `GET`/`POST /management/accounts/{id}/` |

Management pages need the `authorization.view` permission; buttons and switches also check `account.manage`, `account.suspend`, `authorization.assign_role`, `authorization.revoke_role` and `authorization.manage_outbox`. Account changes send the account's `version`; a 409 means someone else changed it first, and the page reloads the version.

## How it works

- **Email** is the sign-in identifier. The backend stores it lowercased, so `Asha@Example.com` and `asha@example.com` are the same account.
- **Phone numbers** (collected at sign-up for WhatsApp contact) are normalised to `+255XXXXXXXXX` (`src/lib/phone.ts`), so `0712 345 678` and `+255712345678` count as the same number for the uniqueness check.
- **Tokens**: the access/refresh pair is kept in `localStorage`. A 401 triggers one shared refresh call; the rotated refresh token is saved (`src/lib/api.ts`).
- **Errors**: DRF field errors appear under each field. Known English server messages are translated (`src/lib/errors.ts`).
- **Language**: the UI starts in Swahili, remembers the visitor's choice, and switches to the account's saved language at sign-in.
- **Layout**: signed-in pages use a navy sidebar (`src/layouts/Sidebar.tsx`, items in `navigation.ts`) that collapses to icons on desktop (remembered per browser) and becomes a slide-in drawer on phones, plus a top bar with breadcrumb, language switch and user menu. Pages are a `PageHeader` followed by cards.
- **Profile fields**: the API uses `preferred_language` and `is_email_verified`; `src/lib/authApi.ts` maps them to `language` and `email_verified` so components don't depend on the wire names.
- **Access**: `/auth/me/` doesn't return roles or permissions yet. As a stopgap, `loadAccess()` in `src/lib/authApi.ts` calls `GET /management/authorization/roles/management/permissions/`, which only Management can read: success means the user is Management with those permissions, 403 means no staff access. Navigation links and management pages appear only when they apply (`src/auth/access.ts`). This is UX only; the API enforces every permission. Replace `loadAccess()` once `/auth/me/` reports roles.
- **Motion**: all animation respects `prefers-reduced-motion`. GSAP (registered once in `src/lib/gsap.ts`) runs page-level sequences and ScrollTrigger reveals; Motion handles component state (pills, sheets, gallery, hover). Never let both animate `transform` on the same element.
- **Public design language**: follows the Horizon Realty reference (serif `font-serif` headlines with a gold accent phrase, navy buttons with small radii, soft `shadow-card` surfaces), with Zoopla's search structure on `/listings`. The map column on search is reserved until the API returns approximate positions (SRC-02).

## Brand

Colours and fonts follow the Oweru brand kit: navy `#0F172A`, gold `#C89128`, off-white `#F8F8F9`; Futura PT for headings, Poppins for body text. Futura PT is a licensed font, so headings fall back to Jost (Google Fonts) until the web font files are added. Gold buttons use navy text because white on gold fails WCAG AA contrast.

Auth page photos are of Dar es Salaam, from Unsplash (free licence): Ali Mkumbwa (sign-in, password pages) and Yoel Winkler (sign-up).

## Known gaps (waiting on the backend)

- `/auth/me/` doesn't report roles, permissions or account category, so Verifiers, Marketers and partners don't see their roles in the UI, and only Management gets role-specific navigation.
- No phone confirmation status in the API, so the account page shows email confirmation only.
- Deletion requests: there's no endpoint to read your own request, withdraw it, or for Management to list and resolve requests. The account page can only send one.
- Phone number and email (the sign-in identifier) can't be changed by the user.
- Partner accounts (local officials, professionals) are created through their own onboarding, not on the staff page.
