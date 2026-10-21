# Oweru Marketplace: design

The visual system, the screen patterns, and the process for designing a new screen. Tokens and components named here exist in `frontend/src`; use them before making new ones.

## 1. Principles

1. **Honest before attractive.** The product's promise is that every property shows exactly what Oweru checked. Design never makes a lower level look like Level 3, never hides a limitation in small print, and shows fees and limits before anyone pays or relies on a result (PRD 3.1).
2. **A cheap Android phone on 3G is the main device.** Design at 360 px wide first. Large tap targets (at least 44 px), short pages, compressed and lazy-loaded images, nothing that needs hover.
3. **Swahili first.** Swahili strings are often 20 to 40 percent longer than English. Layouts must survive the longer text without truncating meaning.
4. **One clear action per step.** Owners, officials and buyers may be using a web app for the first time. Confirmation flows are short steps with one main button.
5. **Calm, trustworthy, Tanzanian.** Navy and gold, real Tanzanian places in photos, plain words.

## 2. Brand tokens

Defined in `frontend/src/index.css` (`@theme`). Use the token names, not raw hex values.

### Colour

| Token | Hex | Use |
|---|---|---|
| `navy` | `#0f172a` | Primary text, primary dark surfaces (sidebar, footer, Level 2 badge), headings |
| `navy-soft` | `#2d3a58` | Secondary text on light surfaces |
| `gold` | `#c89128` | Primary buttons, accents, focus ring, Level 3 |
| `gold-light` | `#e5b972` | Button hover, Level 3 gradient end |
| `paper` | `#f8f8f9` | Page background |
| `mist` | `#dde1e8` | Borders, dividers, quiet fills |
| `muted` | `#55617a` | Captions, helper text |
| `danger` / `danger-soft` | `#b42318` / `#fdecea` | Errors, problem found |
| `success` / `success-soft` | `#1f7a4d` / `#e8f5ee` | Confirmed, passed, resolved |

Contrast rules (WCAG AA):

- **Gold buttons carry navy text.** White on gold fails contrast.
- **Gold text on paper or white fails.** Links are navy with a gold underline (`text-link` utility). Small gold text on light backgrounds uses the darker `#9a6c12` or `#7a5410`.
- Status chips pair a soft tint with a dark text of the same hue (see `pages/staff/ops/ui.tsx`).

### Typography

| Token | Family | Use |
|---|---|---|
| `font-display` | Futura PT (licensed), falling back to Jost | Headings, buttons, labels in caps |
| `font-sans` | Poppins | Body text, forms, tables |
| `font-serif` | Playfair Display | Large public headlines only (home, property page), often with a gold accent phrase. Lining figures are forced so "Level 0" never reads "Level o" |

Fonts load from Google Fonts in `index.html` (Jost, Playfair Display, Poppins). Add the Futura PT web font files when the licence is in place.

Sizes: body 14 to 16 px, never below 12 px for anything a person must read. Numbers that line up in columns use `tabular-nums`.

### Shape and depth

- Buttons and inputs: `rounded-xl`, 48 px tall (`h-12`).
- Public cards: soft lift `shadow-card`, larger `shadow-lift` for hover or featured items. No heavy outlines.
- Staff cards: white, hairline `border-mist/70`, small radius (`rounded-[6px]`). Dense and quiet.
- Chips and badges: `rounded-full`.
- Focus: 2 px gold outline with 2 px offset on every focusable element.

## 3. Components

Shared (`src/components/`):

| Component | Notes |
|---|---|
| `Button` | `primary` (gold, navy text) and `secondary` (white, hairline). Full width in forms, `fullWidth={false}` in toolbars. `loading` shows a spinner and `aria-busy` |
| `TextField`, `SelectField`, `TextAreaField`, `FilesField` | Visible label above the field, error text under it from DRF field errors |
| `Alert` | Inline success, error and info messages near the action they belong to |
| `Card`, `StatTile`, `PageHeader` | Signed-in page building blocks: a `PageHeader` then cards |
| `VerificationBadge` | The only way to show a level (section 5) |
| `ListingCard`, `ResultCard`, `PhotoCard` (+ skeletons) | Property cards for home, search and featured |
| `MapPicker` | Leaflet pin picker |
| `LanguageSwitch`, `UserMenu`, `Logo`, `WhatsAppHelp` | Shell pieces |
| `icons.tsx` | Line icons drawn for this project. Add new icons here in the same 24 px, stroke style. Never use emoji as icons |
| `Stagger` | Entrance stagger for lists |

Area kits: `pages/deals/ui.tsx` (`CountUp`, `CopyValue`, `ThreeStepBar`, `TickTimeline`, `NumberedProgress`, `SidePanel`, payment and payout chips), `pages/staff/ops/ui.tsx` (status chips, `RadioTabs`, `SearchBox`, `RowTable`), `pages/lister/ui.tsx` (status pills, `CountCard`, `Panel`, `Notice`, `RowMenu`), `pages/staff/marketing/ui.tsx`, `pages/public/services/ServiceUi.tsx` (free check, complaints, full check pages).

## 4. Layouts and page patterns

### Public site (`PublicLayout`)

Light paper background, a white header with the logo and language switch, a navy footer, and a floating navy tab bar on phones (Home, Search, Check, Help, Account).

- **Home**: serif headline with a gold accent phrase, search entry, the four levels explained, recent listings, how buying works.
- **Search**: location bar, filter pills that open panels, sort, results grid, filters kept in the URL. Map positions are approximate.
- **Property page**: gallery, price and facts, verification panel with the exact SRD wording, lister card, WhatsApp contact, enquiry and viewing request, full check entry.
- **Services** (free check, complaints, full check): a `ServiceHeader`, then a form or status in one or two columns.
- **Confirmation links** (`/confirm`): a single white card, centred, no site navigation needed. One step per screen: figure first, details as rows, one strong button and a quiet secondary (decline goes through a confirm sheet). Ends on a calm done card with a reference to screenshot.

### Sign in and sign up (`AuthLayout`)

Split screen: form on one side, a photo of Dar es Salaam on the other (hidden on phones).

### Signed-in work (`AppLayout`)

Navy sidebar grouped by job (Operations, Marketing, Listing, Account, Management) that collapses to icons on desktop and slides in on phones. Top bar with breadcrumb, language and user menu.

- **Staff desks** (complaints, full checks, location checks, identities, outbox): a summary strip of counts, radio tabs by status, search, and a row table. Rows fold into stacked cards on phones. Detail pages put the evidence (map, photos, documents) on the left and the decision on the right.
- **Lister area**: count cards, listings table with status pills and a row menu, a map view, the listing editor with a live preview.
- **Market panel**: filter row first, then charts with legends and tooltips, a regions map, and an Excel export.

## 5. Verification levels in the UI

The level badge and panel follow SRD 10 exactly. These are product rules, not style choices.

| Level | Badge style | Label source |
|---|---|---|
| 3 Oweru Verified | Gold gradient, navy text, shield icon, soft gold glow | `levels.short.3`; full label "Oweru Verified: full check completed [date]. Valid until [date]." |
| 2 Location Checked | Navy, white text, pin icon | Must say it is not ownership verification |
| 1 Lister Verified | White, navy text, hairline ring, person icon | "Listed by [name], identity verified by Oweru" |
| 0 Listed | Paper, muted text, hairline ring | "Listed by [name]. Not verified by Oweru" |

- Gold, the shield and the words "Oweru Verified" belong to Level 3 only. Do not use the gold gradient or the shield for anything else that could be read as verification.
- Owner listings below Level 3 add: "[name] states they are the owner. Ownership has not been verified."
- Never write "guarantee" or "Oweru Agent". Agent profiles state the agent is independent and acts for the owner.
- Free check and Level 2 always say they are not ownership verification. Verdicts based on Oweru's records state their coverage ("among properties Oweru has on record").

## 6. Motion

- `motion/react` for component state: button taps, sheets, tabs, step changes. GSAP with `useGSAP` (registered once in `lib/gsap.ts`, always scoped to a ref) for page entrances and scroll reveals.
- Never let both libraries animate `transform` on the same element.
- Durations 150 to 300 ms for interface feedback; exits faster than entrances.
- Everything respects `prefers-reduced-motion`.
- Motion explains a change (a step moving forward, a row arriving). No decorative loops on working screens.

## 7. Imagery and maps

- Photos of real Tanzanian places and properties. Credit free-licence photos in the frontend README. Never keep real people's camera images (selfies, ID photos) outside the identity flow.
- Public maps show rounded positions only. Staff location checks show the exact pin with street and satellite layers. Maps never suggest they prove ownership (MAP-09).
- Listings maps may use the muted grey tile style (`map-tiles-muted`) so pins stand out.

## 8. Copy

- Every string lives in `src/i18n/sw.ts` and `en.ts`, with identical keys. Swahili is written first, not translated last.
- Plain words. Short sentences. Name the next step ("Thibitisha na tuma", "Confirm and send").
- No em dash in interface copy. Use a comma, colon, parentheses or a full stop.
- Money: `TSh` with thousands separators, no decimals. Dates: short local format (`formatShortDate`).
- Errors say what happened and what to do. Never show raw codes (`UNDER_FINAL_REVIEW`) or internal ids to the public.

## 9. Accessibility checklist

- Every input has a visible label; errors sit next to the field.
- Icon-only buttons have an `aria-label`.
- Keyboard: every action reachable, visible gold focus ring, sheets trap and return focus.
- Status is never colour alone: chips carry words, levels carry icons and words.
- Touch targets at least 44 by 44 px with 8 px between them.
- Tables have `scope` on headers; on phones they become labelled stacked rows.

## 10. Designing a new screen

Every new screen goes through the same steps:

1. **Find references.** Collect real product screens from Dribbble and Pinterest that solve the same job (for example a request with Decline and Approve, a payout setup flow).
2. **Publish a picking board.** Group the references by part of the flow, say what each one would bring to Oweru and what would be left out, and share it so the product owner can pick.
3. **Wait for the pick.** The product owner picks references or says to go with the recommended ones.
4. **Build to match the picks.** Match the layout, structure and hierarchy of the picked references closely, recoloured to navy and gold and using the components above. Note the reference codes in a comment at the top of the screen (for example `// K8: read, then Accept or Decline`).
5. **Check it on a phone width and in both languages**, then against sections 5, 8 and 9 of this document.

Reference families already used: Horizon Realty (public pages and headline style), Zoopla (search structure), the W series (staff desks), the L series (lister area), the K series (confirmation links), the D series (deals and money).
