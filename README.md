# TalentMatch — Freelance Marketplace with Subscriptions & Payments

Companies subscribe to a plan, post full job descriptions and get freelancers **ranked by fit**. Freelancers
publish profiles, upload their CV and sell fixed-price services. Payments run through **Razorpay**; the platform
holds the money and an admin releases the freelancer's payout after the client approves the work. A
**control room** shows revenue, users, payments, payouts and an audit trail.

Built for a global audience: INR / USD / EUR / GBP pricing (Razorpay for INR, Stripe for the rest), English / हिन्दी /
Español interface, countries, timezones and working hours, reviews and verified badges, private messaging, in-app and
email notifications.

Stack: FastAPI · SQLAlchemy · Alembic · PostgreSQL (Neon) / SQLite · React 19 · Vite · Tailwind CSS 4 ·
Razorpay (+ Route) · Stripe · WebSockets · Docker · Render · Vercel · GitHub Actions.

---

## Run it locally (5 minutes)

**Windows:** install Python 3.10+ (tick "Add to PATH"), then double-click **`SETUP_AND_START.bat`**.
**macOS / Linux:** `./start.sh`

The first run creates a virtual environment, installs dependencies, loads demo data and opens
**http://localhost:8000**. The React app is already built (`frontend/dist`), so Node.js isn't needed to run it.

| Demo account | Email | Password |
|---|---|---|
| Admin (control room) | admin@talentmatch.dev | Admin@12345 |
| Client — Premium plan | priya@technova.in | Demo@1234 |
| Client — Free plan | arjun@buildright.in | Demo@1234 |
| Freelancer (payouts set up) | rahul.verma@mail.com | Demo@1234 |
| Freelancer (no payout details yet) | rohan.das@mail.com | Demo@1234 |
| Client in the US (USD billing) | emily@northwind.io | Demo@1234 |
| Freelancer in Spain (EUR) | lucia.fernandez@mail.com | Demo@1234 |

To start with an empty database, stop the server and delete `backend/talentmatch.db`.
API docs (Swagger): http://localhost:8000/docs

### Frontend development
```bash
cd backend && python -m uvicorn app.main:app --port 8000     # terminal 1
cd frontend && npm install && npm run dev                     # terminal 2 → http://localhost:5173
```
Vite proxies `/api` and `/ws` to the API, so sign-in cookies work in development.

---

## What each role can do

**Clients (companies)**
- Sign up → their own company is created on the **Free** plan (a matching company name never joins another company).
- Post job descriptions: overview, responsibilities, requirements, skills, minimum experience, fixed/hourly budget,
  remote/hybrid/on-site, deadline. Attach PDFs / Word files or links (Google Drive, Notion, Figma…).
- See **ranked matches** with matched and missing skills; review **proposals**; shortlist, decline or **hire**.
- Hiring or buying a service creates an **order** → pay with Razorpay → approve the delivery or request changes.
- Upgrade / downgrade the plan from **Plan & billing**, with full payment history.

**Freelancers**
- Profile with headline, bio, rate, availability, links; **upload a CV (PDF)** and skills, experience and phone are filled in.
- Attach portfolio files and certificates; publish **fixed-price services**.
- **Find work**: open jobs ranked against their profile; apply with a cover letter and bid.
- Deliver orders with notes and files; add bank / UPI payout details and get paid automatically on approval.

**Admins — control room**
- KPIs: money collected, MRR, platform fees, payouts to release; revenue and sign-up chart; plan mix; order pipeline.
- Users (search, disable — which also ends their sessions), payment ledger, orders and **payouts** (held, released,
  needs attention, retry, manual),
  job and service moderation, **audit log** (sign-ins, payments, payouts, deletions, admin actions), re-run matching.

**Everyone**
- **Messages** — private client ↔ freelancer threads with live delivery and unread counts. Free-plan clients can message
  freelancers who applied to their jobs; paid plans can message anyone; freelancers can message clients they applied to.
- **Notifications** — bell with unread count, live pop-ups, and email (first unread message per thread only, so
  bursts don't flood inboxes). Users can turn email off.
- **Reviews** — after an order is approved, each side rates the other once (1–5 + comment). Ratings show on profiles,
  cards, proposals and job pages.
- **Badges** — *Verified* (identity checked by an admin), *Payouts set up*, *Top rated* (4.5+ from 3+ reviews).
- **Countries & time** — country, timezone, working hours and languages on profiles; "3:42 PM local (+5h 30m from
  you)"; filter talent by region, country, language, verified; sort by rating or rate.
- **Languages** — English, हिन्दी, Español. The choice is saved on the account and follows the user across devices.
- **Forgot password** — single-use emailed link (30 minutes); resetting signs out every device.

### Plans
| Plan | INR | USD | EUR | GBP | Open jobs | Matches visible per job | Contact details | Messaging |
|---|---|---|---|---|---|---|---|---|
| Free | ₹0 | $0 | €0 | £0 | 2 | top 3 | masked | applicants only |
| Premium | ₹999 | $15 | €14 | £12 | 20 | top 25 | shown | anyone |
| Enterprise | ₹4,999 | $59 | €55 | £47 | unlimited | all | shown | anyone |

A client's billing currency follows their country at sign-up (India → INR, UK → GBP, euro area → EUR, else USD) and
can be changed in Account. Jobs, services and orders each carry their own currency.

Edit them in `backend/app/core/plans.py`. On orders the platform keeps a 10% fee (`PLATFORM_FEE_PERCENT`).

---

## Payments (Razorpay for INR, Stripe for USD / EUR / GBP)

| Currency | Provider | How the client pays |
|---|---|---|
| INR | Razorpay | Razorpay Checkout pop-up (UPI, cards, netbanking) → server verifies the signature |
| USD / EUR / GBP | Stripe | Redirect to Stripe Checkout → back on `/payments/return` → server re-reads the session from Stripe |

Both providers' webhooks credit the payment too (so closing the browser doesn't lose it), with the amount and currency
checked; crediting is idempotent. If only Razorpay is configured, INR works and other currencies are refused — never
silently simulated. If only Stripe is configured, INR also goes through Stripe.

**Stripe setup:** create keys (Developers → API keys), set `STRIPE_SECRET_KEY`; add a webhook endpoint
`https://<your-site>/api/v1/payments/stripe/webhook` with events `checkout.session.completed`,
`checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `checkout.session.expired`,
and set its signing secret as `STRIPE_WEBHOOK_SECRET`. `FRONTEND_URL` must be your site's URL (Stripe returns there).

### Razorpay

Without any keys the app runs in **demo mode**: a clearly labelled simulated checkout where you can choose success
or failure. No money moves. To use Razorpay:

1. Create a Razorpay account and copy the **test** Key ID and Key Secret (Settings → API Keys).
2. Set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` on the API server. The app switches to Razorpay Checkout automatically.
3. Add a webhook in Razorpay pointing to `https://<your-api>/api/v1/payments/webhook` with events
   `payment.captured`, `order.paid`, `payment.failed`, and set the same secret as `RAZORPAY_WEBHOOK_SECRET`.

How it works: the server creates a Razorpay order for the exact amount → the browser opens Checkout →
`/payments/verify` checks the HMAC-SHA256 signature → the plan or order is fulfilled. The webhook does the same
fulfilment (with an amount check), so a payment is credited even if the browser closes; fulfilment is idempotent.
Amounts are stored in paise.

### Automatic freelancer payouts (Razorpay Route)

1. The client pays the full order amount.
2. The freelancer's share (order value minus the platform fee) is **transferred from that payment to the
   freelancer's Razorpay Route linked account, on hold**.
3. When the client approves the delivery, the hold is lifted and Razorpay settles the money to the freelancer's bank
   account or UPI ID on the linked account's settlement schedule.

Freelancers add a bank account (number + IFSC) or a UPI ID once, under **Payouts**. The details go straight to
Razorpay, which creates the linked account; TalentMatch stores only a masked copy (IFSC + last 4 digits, or the UPI ID).
If a freelancer adds details late, money for paid orders is secured and already-approved orders are paid out at once.

If a payout can't go automatically (no details yet, Route off, or Razorpay rejects it), the order shows **Pending** or
**Failed** under *Control room → Orders & payouts → Needs attention*, with the reason. The admin can **Retry via
Route** or pay outside the app and record it with **Paid manually**. A transfer is never created twice for the same order.

To switch it on:
1. Ask Razorpay to enable **Route** on your account (Dashboard → Route, or your account manager).
2. Set `RAZORPAY_ROUTE_ENABLED=true` (with the Razorpay keys above).
3. In the Razorpay webhook, also subscribe to `transfer.processed`, `transfer.failed`, `product.route.activated`,
   `product.route.under_review`, `product.route.needs_clarification`, `account.activated` and `account.needs_clarification`.

Notes: Razorpay's gateway fee is charged to the platform's account, not deducted from the freelancer's share. Bank
accounts are verified by a penny drop (about 10–15 minutes); UPI IDs are verified immediately. In demo mode payouts
are simulated with `acc_demo_…` / `trf_demo_…` IDs.

---

## How production works

```
Browser ──► Vercel (React app, CDN)
              │  /api/*  is forwarded (vercel.json) ──► Render: FastAPI in Docker ──► Neon: PostgreSQL
              └─ live updates: wss://<render>/ws (token auth) ─────┘        │
                                                                           ├─► Razorpay (INR, Route payouts)
                                                                           ├─► Stripe (USD / EUR / GBP)
                                                                           └─► SMTP (emails)
```
- **One site for the browser.** Vercel forwards `/api/*` to Render, so the sign-in cookie is first-party and works
  in Safari and with third-party cookies blocked. WebSockets connect straight to Render (they use the access token,
  not the cookie).
- **Database.** Neon Postgres. Migrations run automatically every time the API starts (`alembic upgrade head`), so a
  deploy that changes the schema needs no manual step. Uploaded files are stored in Postgres too, so nothing is lost
  when Render restarts the container.
- **Money.** Payments land in your Razorpay / Stripe accounts. INR order shares move to freelancers' Route accounts on
  hold and are released on approval; international orders are paid out manually from the control room.
- **Free tiers.** Render's free API sleeps after ~15 minutes idle; the first request after that takes up to a minute
  (the app says "try again in a few seconds"). Point an uptime monitor at `/health` to keep it awake, or move to a paid
  instance when you have real traffic.

## Deploy (Vercel + Render + Neon)

1. **Neon** — create a project (region near your users, e.g. Singapore for India) and copy the connection string
   (`postgresql://…?sslmode=require`).
2. **Render** — *New → Blueprint*, pick this repo (it reads `render.yaml`). Fill in `DATABASE_URL` (Neon),
   `ADMIN_EMAIL`, `ADMIN_PASSWORD`. Leave `CORS_ORIGINS` / `FRONTEND_URL` for step 4. `SECRET_KEY` is generated.
   Wait for the deploy, then open `https://<your-api>.onrender.com/health` → `{"status":"ok"}`.
3. **Vercel** — edit `frontend/vercel.json`: replace `REPLACE-WITH-YOUR-RENDER-URL` with your Render service name and
   push. Then *Add New → Project*, import the repo, **Root Directory `frontend`**, framework Vite. Add env
   `VITE_WS_URL=wss://<your-api>.onrender.com`. Deploy.
4. **Back on Render**, set `CORS_ORIGINS` and `FRONTEND_URL` to your Vercel URL (e.g. `https://talentmatch.vercel.app`).
5. Optional: Razorpay keys (+ `RAZORPAY_ROUTE_ENABLED` after Razorpay enables Route), Stripe keys, SMTP settings.
   Webhook URLs use your **Vercel** address, e.g. `https://talentmatch.vercel.app/api/v1/payments/webhook`.
6. Sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD` → control room. The production database starts empty (no demo data).

**Single server instead:** `docker compose up --build` runs Postgres plus the all-in-one image (API + built app)
on http://localhost:8000.

### Configuration
| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | SQLite file | Postgres URL in production (Neon `postgresql://` works as is) |
| `SECRET_KEY` | random per start | Signs access tokens — **set it in production** |
| `ENV` | development | `production` → secure cross-site cookies |
| `CORS_ORIGINS` | localhost:5173 | Allowed frontend origins (comma-separated) |
| `FRONTEND_URL` | http://localhost:8000 | Public site URL, used in emails and Stripe return links |
| `COOKIE_SAMESITE` | lax (dev) / none (prod) | `lax` when the API is behind the Vercel `/api` proxy |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | — | Creates the first admin on startup |
| `SIGNUP_MODE` | open | `closed` stops new sign-ups |
| `RAZORPAY_KEY_ID` / `_KEY_SECRET` / `_WEBHOOK_SECRET` | — | Enable real payments |
| `RAZORPAY_ROUTE_ENABLED` | false | Automatic freelancer payouts through Razorpay Route |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | — | Enable USD / EUR / GBP payments |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `EMAIL_FROM` | — | Send emails (otherwise written to the server log) |
| `PASSWORD_RESET_MINUTES` | 30 | Reset link lifetime |
| `VITE_WS_URL` (Vercel) | — | `wss://` address of the API for live updates |
| `PLATFORM_FEE_PERCENT` | 10 | Fee kept from each order |
| `MATCH_THRESHOLD` | 50 | Minimum score to count as a match |
| `MAX_UPLOAD_MB` | 10 | Upload limit |

---

## Security
- Passwords: PBKDF2-SHA256, 390,000 iterations, per-user salt.
- Sessions: 30-minute access token kept in memory (not localStorage); httpOnly refresh cookie stored only as a
  SHA-256 hash; rotated on every use; reusing an old refresh token ends every session for that user;
  sliding 30 days, 90-day hard limit; "sign out everywhere"; changing the password signs out other devices.
- Rate limits on sign-in, sign-up, refresh, checkout and uploads.
- Every write checks ownership; other tenants' jobs, orders and files return 404 (existence isn't revealed).
- Uploads: type allow-list, size cap, PDF magic-byte check, served with `nosniff` and `no-store`.
  Files are stored in Postgres, so they survive restarts on hosts with temporary disks.
- Links must be `http(s)`; external links open with `noopener noreferrer nofollow`.
- Security headers on every response; audit log of sensitive actions.

## Tests
```bash
cd backend && python -m pytest -q                       # 56 tests (SQLite)
TEST_DATABASE_URL=postgresql+psycopg2://user@host/db python -m pytest -q   # same suite on Postgres
cd frontend && npm test                                  # 16 tests
```
GitHub Actions runs the backend suite on SQLite **and** Postgres, plus the frontend tests and build, on every push.

## Limitations
- Refunds after payment aren't automated (they would also need a Route transfer reversal).
- Razorpay Route is tested against a mocked API; run one real test-mode payout after enabling Route.
- Rate limits are in memory, so they apply per API instance.
- On Render's free tier the API sleeps after inactivity, so the first request after a pause is slow.
- Scanned (image-only) CVs aren't read. Optional OCR plugins exist in `app/plugins/ingestion` but aren't installed by default.
- Hindi and Spanish translations were written with AI help — have native speakers review them before launch. User
  content (job descriptions, messages, reviews) isn't translated.
- International (non-INR) orders are paid out to freelancers manually; Route payouts are INR only.
- Rate limits use X-Forwarded-For and live in memory (per instance); move them to Redis with a trusted client-IP header
  before heavy traffic.
- Stripe and Razorpay are tested against mocked APIs; run one real test-mode payment of each after adding keys.

## Project layout
```
backend/   FastAPI app (app/), Alembic migrations, tests/, seed_demo.py, Dockerfile (API only)
frontend/  React + Vite + Tailwind app, vercel.json
Dockerfile, docker-compose.yml   all-in-one image + Postgres
render.yaml, .github/workflows/ci.yml
```
