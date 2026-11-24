Build the TalentMatch case-study page at /projects/talentmatch in the portfolio (and use the same facts for its home-page card). Use ONLY these facts; never invent numbers. Accent: blue.

## Header
- Title: TalentMatch
- One line: A global freelance marketplace where companies post job descriptions, get freelancers ranked by fit, then hire, chat and pay in INR, USD, EUR or GBP.
- Status chip: Demo — payments in Razorpay test mode
- Links: Live TODO (Vercel URL) · Code TODO (GitHub URL)
- Home-card metrics: 72 automated tests · 4 currencies · 3 languages

## The problem
Small companies hiring freelancers wade through profiles that don't fit, chase contact details, and pay strangers with no protection. Freelancers waste time applying to jobs they don't match. A plain listings board doesn't help either side decide.

## What it does
1. A company signs up (on its own account, even if another company has the same name) and posts a full job description: overview, responsibilities, requirements, skills, experience, budget, work mode, deadline, plus PDFs or Drive/Notion links.
2. Every public freelancer is scored against it (skills 70%, experience 30%); the company sees a ranked list with matched and missing skills.
3. Freelancers upload a CV (PDF) and their skills and experience are filled in; they see open jobs ranked for them and apply with a bid.
4. The company hires (or buys a fixed-price service) and pays through Razorpay. The freelancer's share is moved to their Razorpay Route account on hold, and released automatically when the company approves the delivery.
5. Subscription plans (Free / Premium ₹999 · $15 / Enterprise ₹4,999 · $59) limit open jobs, visible matches, contact details and who a client can message.
6. Clients and freelancers message each other privately, get in-app and email notifications, and review each other after each order; ratings and verified badges build trust.
7. The interface works in English, Hindi and Spanish; profiles show country, local time and working hours.

## Architecture (draw as an inline SVG diagram, animated draw-in)
React app (Vercel, which forwards /api to the API so the sign-in cookie stays first-party) → FastAPI API (Render, Docker) → PostgreSQL (Neon), with Razorpay (INR + Route payouts), Stripe (USD / EUR / GBP) and SMTP on the side.
Hiring path: job posted → matching runs against every profile → ranked matches → proposal → order → Razorpay order → Checkout → server verifies the HMAC signature (or the webhook arrives) → order paid → freelancer's share transferred to their Route linked account on hold → delivered → approved → hold released → Razorpay settles to the freelancer's bank / UPI.
Live notifications go out over a WebSocket authenticated with the access token.

## Key decisions and trade-offs
- Matching kept in sync on every change: matches are recomputed when a job or a profile changes, so a freelancer who joins after a job is posted still appears. Trade-off: writes do more work instead of a nightly batch.
- One fulfilment function for the browser callback and the webhook: whichever arrives first credits the payment; the other is a no-op. The webhook also checks the paid amount. Trade-off: both paths have to be kept identical.
- Escrow through Razorpay Route, not the platform's bank: the freelancer's share is parked in their own linked account on hold at payment time and released on approval, so money never has to be paid out by hand. Payouts never block a payment: if Route fails, the order is flagged for an admin to retry or pay manually, and a transfer is never created twice for one order (it is looked up by order ID before creating). Trade-off: the freelancer must add payout details, and refunds after payment would need a transfer reversal (not built).
- Card and bank details never stored: freelancers' account numbers go straight to Razorpay; only IFSC + last 4 digits are kept.
- Messaging respects the plans: Free clients can only message freelancers who applied to their jobs, so contact masking can't be bypassed through chat.
- Emails don't flood: a message triggers an email only if it's the first unread one in that thread.
- Money in paise: amounts are stored as integers to avoid rounding errors.
- Files stored in Postgres, not on disk: the API host has a temporary disk, so uploads would vanish on restart; keeping them in the database also deletes and backs them up with their owner. Trade-off: database size grows with uploads (capped at 10 MB per file, 20 per item).
- Tenant isolation on every write: ownership is checked on each job, order, service and file; another tenant's records return 404 so their existence isn't revealed. Covered by tests.
- Two payment providers, routed by currency: Razorpay for INR, Stripe Checkout for USD / EUR / GBP, both fulfilled by the same idempotent function from the browser return or the webhook. Once any real provider is configured, a currency without one is refused, never simulated. Trade-off: international orders are paid out manually.
- One site for the browser: Vercel forwards /api to Render so the refresh cookie is first-party, which keeps users signed in on Safari and with third-party cookies blocked. WebSockets go straight to the API with the access token.
- Translation as a thin layer: the UI is written in English and a dictionary + pattern engine translates rendered interface text, skipping anything marked as user content. The Hindi/Spanish dictionary loads only when chosen (14.5 kB gzipped). Trade-off: translations need a native-speaker review.
- Demo payment mode: with no provider configured at all, checkout is simulated and clearly labelled, so the whole flow can be shown without real money.

## Security and reliability
- Roles: admin, client, freelancer; admin cannot be self-assigned at sign-up.
- Passwords hashed with PBKDF2-SHA256 (390,000 iterations).
- Sessions: 30-minute access tokens in memory; httpOnly refresh cookie stored only as a SHA-256 hash, rotated on every use; reusing an old token ends all of that user's sessions; sliding 30 days, 90-day hard limit; "sign out everywhere"; password change signs out other devices.
- Disabling a user in the control room ends their sessions immediately.
- Rate limits on sign-in, sign-up, refresh, checkout, uploads, password reset and messages; identical replies for unknown emails on sign-in and forgot-password (no account enumeration).
- Password reset: 32-byte single-use link stored as a SHA-256 hash, 30-minute expiry, only the newest link works, reset signs out every device.
- Stripe webhooks verified with timestamped HMAC signatures (replays older than 5 minutes rejected).
- Upload type allow-list, size cap, PDF signature check; audit log of sign-ins, payments, payouts, deletions and admin actions.

## Frontend craft
React 19 + Tailwind 4 with no UI, chart, animation or i18n libraries: hand-built SVG hero (lines draw in to ranked freelancers, drifting gradient, pulsing top match), page transitions, scroll reveals with stagger, count-up numbers, skeleton loaders, sliding tab indicator, animated check mark on payment success, SVG revenue/sign-up chart per currency, animated match-score rings, and full reduced-motion support. The motion set adds about 2.4 kB gzipped; initial JavaScript is 85.5 kB gzipped.

## Quality
- 56 backend tests (pytest) run on both SQLite and PostgreSQL + 16 frontend tests (Vitest), in GitHub Actions on every push. Razorpay Route and Stripe are tested against mocked APIs, checking the exact calls, signatures and amounts.
- End-to-end browser runs across all three roles: sign-up, CV upload, apply, hire, pay, deliver, approve, automatic payout, admin retry, cross-border chat with live delivery, reviews, password reset by email link, Spanish and Hindi UI, region filters, per-currency control room.
- 3 Alembic migrations; 19 tables; 101 API endpoints.

## Limitations (state plainly)
- Route has been tested against a mocked API; it needs one real test-mode run once Razorpay enables Route.
- Refunds after payment aren't automated.
- International orders are paid out manually; Hindi and Spanish need a native-speaker review.
- Per-IP rate limits live in memory, so they hold only on a single API instance.
- Scanned (image-only) CVs aren't read.
- No email notifications or password-reset email yet.
- Free-tier hosting: the API sleeps when idle, so the first request is slow.

## What's next
Refunds with Route transfer reversals; Stripe Connect for automatic international payouts; file sharing inside chat; more languages; Redis for shared rate limits and a background worker for emails.

## Stack chips
FastAPI · Python · PostgreSQL · Neon · SQLAlchemy · Alembic · React · Vite · Tailwind · Razorpay · Stripe · WebSockets · i18n · Docker · Render · Vercel · GitHub Actions

Leave a demo-video slot under the header (TODO: talentmatch-demo.mp4).
