# Oweru Marketplace frontend

React web app for the Oweru Marketplace backend in [`../backend/`](../backend/README.md). It covers the accounts module (M02): sign up, sign in, forgot password, reset password and a read-only account page; and the Management screens for roles and permissions (M03).

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

Port 5173 is fixed on purpose: the backend's `CORS_ALLOWED_ORIGINS` and `PASSWORD_RESET_URL` point to it.

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
| `/register` | Sign up with name, email, phone and password; language comes from the header switch | `POST /auth/register/`, then `POST /auth/login/` |
| `/login` | Sign in with email and password | `POST /auth/login/` |
| `/forgot-password` | Request a reset link by email, WhatsApp help for people who can't reach their inbox | `POST /auth/password/reset/` |
| `/reset-password?uid=&token=` | Set new password from the emailed link | `POST /auth/password/reset/confirm/` |
| `/account` | Account details and roles (signed in only) | `GET /auth/me/` |
| `/management/roles` | Roles × permissions matrix; WhatsApp outbox switches for Verifier and Marketer | `GET /management/authorization/roles/…/permissions/`, `PUT …/roles/{role}/outbox-send/` |
| `/management/staff` | Find an account by email; give or remove Verifier and Marketer roles | `GET …/users/?email=`, `GET …/users/{id}/roles/`, `POST …/roles/assign/` and `…/revoke/` |

Management pages need the `authorization.view` permission; buttons and switches also check `authorization.assign_role`, `authorization.revoke_role` and `authorization.manage_outbox`.

## How it works

- **Email** is the sign-in identifier. The backend stores it lowercased, so `Asha@Example.com` and `asha@example.com` are the same account.
- **Phone numbers** (collected at sign-up for WhatsApp contact) are normalised to `+255XXXXXXXXX` (`src/lib/phone.ts`), so `0712 345 678` and `+255712345678` count as the same number for the uniqueness check.
- **Tokens**: the access/refresh pair is kept in `localStorage`. A 401 triggers one shared refresh call; the rotated refresh token is saved (`src/lib/api.ts`).
- **Errors**: DRF field errors appear under each field. Known English server messages are translated (`src/lib/errors.ts`).
- **Language**: the UI starts in Swahili, remembers the visitor's choice, and switches to the account's saved language at sign-in.
- **Layout**: signed-in pages use a navy sidebar (`src/layouts/Sidebar.tsx`, items in `navigation.ts`) that collapses to icons on desktop (remembered per browser) and becomes a slide-in drawer on phones, plus a top bar with breadcrumb, language switch and user menu. Pages are a `PageHeader` followed by cards.
- **Access**: `/auth/me/` returns the user's effective `roles` and `permissions`. Navigation links and management pages appear only when they apply (`src/auth/access.ts`). This is UX only; the API enforces every permission.
- **Motion**: all animation respects `prefers-reduced-motion`.

## Brand

Colours and fonts follow the Oweru brand kit: navy `#0F172A`, gold `#C89128`, off-white `#F8F8F9`; Futura PT for headings, Poppins for body text. Futura PT is a licensed font, so headings fall back to Jost (Google Fonts) until the web font files are added. Gold buttons use navy text because white on gold fails WCAG AA contrast.

Auth page photos are of Dar es Salaam, from Unsplash (free licence): Ali Mkumbwa (sign-in, password pages) and Yoel Winkler (sign-up).

## Known gaps (waiting on the backend)

- No logout endpoint: signing out clears tokens in the browser only; the refresh token stays valid until it expires (7 days).
- No profile update or account deletion endpoint (ACC-08), so the account page is read-only.
- No email confirmation (ACC-05) or WhatsApp phone confirmation page yet.
- No staff account creation (ACC-06): operational accounts are created by the technical team, so the staff page can only manage roles on existing accounts.
