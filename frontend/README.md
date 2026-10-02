# Oweru Marketplace frontend

React web app for the Oweru Marketplace backend in this repository. It currently covers the accounts module (M02): sign up, sign in, forgot password, reset password and a read-only account page.

## Stack

- React 19 + TypeScript, built with Vite
- Tailwind CSS v4 (brand tokens in `src/index.css`)
- Motion (`motion/react`) for component and page transitions
- GSAP with `@gsap/react` (`useGSAP`) for headline and reveal timelines
- React Router, i18next (Swahili default, English)

## Run locally

1. Start the Django API on `http://127.0.0.1:8000` (see the repository README).
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
| `/account` | Account details (signed in only) | `GET /auth/me/` |

## How it works

- **Email** is the sign-in identifier. The backend stores it lowercased, so `Asha@Example.com` and `asha@example.com` are the same account.
- **Phone numbers** (collected at sign-up for WhatsApp contact) are normalised to `+255XXXXXXXXX` (`src/lib/phone.ts`), so `0712 345 678` and `+255712345678` count as the same number for the uniqueness check.
- **Tokens**: the access/refresh pair is kept in `localStorage`. A 401 triggers one shared refresh call; the rotated refresh token is saved (`src/lib/api.ts`).
- **Errors**: DRF field errors appear under each field. Known English server messages are translated (`src/lib/errors.ts`).
- **Language**: the UI starts in Swahili, remembers the visitor's choice, and switches to the account's saved language at sign-in.
- **Motion**: all animation respects `prefers-reduced-motion`.

## Brand

Colours and fonts follow the Oweru brand kit: navy `#0F172A`, gold `#C89128`, off-white `#F8F8F9`; Futura PT for headings, Poppins for body text. Futura PT is a licensed font, so headings fall back to Jost (Google Fonts) until the web font files are added. Gold buttons use navy text because white on gold fails WCAG AA contrast.

Auth page photos are of Dar es Salaam, from Unsplash (free licence): Ali Mkumbwa (sign-in, password pages) and Yoel Winkler (sign-up).

## Known gaps (waiting on the backend)

- No logout endpoint: signing out clears tokens in the browser only; the refresh token stays valid until it expires (7 days).
- No profile update or account deletion endpoint (ACC-08), so the account page is read-only.
- No email confirmation (ACC-05) or WhatsApp phone confirmation page yet.
- `/auth/me/` does not return roles, so role-based dashboards cannot be built yet.
