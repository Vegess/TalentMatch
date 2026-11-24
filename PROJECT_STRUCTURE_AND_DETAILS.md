# TalentMatch v3 — structure & rules (for planning further work)

See README.md for running, deploying and configuration.

## Layout
```
backend/
  app/main.py                 app, routers, security headers, SPA serving, startup (migrations, admin bootstrap, rematch)
  app/core/                   config (env), database + run_migrations, security (hashing, JWT, refresh tokens),
                              deps (current user / role guards), ratelimit, plans, plugin loader/interface
  app/models/                 users, auth_sessions, clients, consultants (freelancer profiles), jobs, matches,
                              subscriptions, services, proposals, orders, payments, documents, document_blobs, audit_logs
  app/schemas/                Pydantic request models (auth, profiles, marketplace)
  app/services/               matching, subscriptions, payments (Razorpay + fulfil), access (ownership rules),
                              serializers, realtime (WebSocket fan-out), cv_parser, uploads, audit, pdfgen
  app/api/v1/endpoints/       auth, freelancers, clients, jobs (+ proposals on a job), proposals, services, orders,
                              payments, subscriptions, documents, admin (control room), tools, websockets
  app/plugins/                ingestion (pdf, optional OCR) + ranking (standard_weighted)
  migrations/                 Alembic (0001 initial schema, 0002 route payouts, 0003 trust + global)
  tests/                      56 pytest tests; TEST_DATABASE_URL runs them on Postgres
  seed_demo.py                demo marketplace (idempotent)
frontend/
  src/lib/                    api (fetch + silent refresh), auth context, hooks, realtime, format (money/geo),
                              i18n (engine) + i18n-dict (Hindi/Spanish, lazy-loaded) (+ tests)
  src/components/             ui kit, Layout (public + role app shell + guards), Checkout (Razorpay/Stripe/demo),
                              Motion (count-up, reveal, skeletons, success mark), Trust (stars, badges, place),
                              Notifications (bell),
                              Documents, Charts (SVG), Cards, Forms
  src/pages/                  public/, client/, freelancer/, shared/ (orders, account), admin/ (control room)
```

## Core rules
- Roles: admin | client | freelancer. Sign-up creates a Client (company, FREE plan) or a Consultant profile.
  A freelancer signing up with an email an admin already used claims that profile.
- Matching: skills 70% + experience 30%, stored if ≥ MATCH_THRESHOLD, only for open jobs with required skills and
  public profiles. Recomputed on every job/profile change, on demand, and at startup.
- Plans (core/plans.py) cap open jobs, visible matches and contact details. Paid plans start only after payment
  (or an admin grant). Expired plans are marked on read.
- Orders: pending_payment → in_progress (paid) → delivered → completed. Payout status: none → held (Route transfer
  on hold, created at payment) → released (hold lifted on approval). pending/failed = needs admin retry or manual payout.
  All Route logic is in services/payouts.py (modes: razorpay | demo | off); never blocks a payment.
  Unpaid orders can be cancelled; delivered work can be sent back for changes. Fee = PLATFORM_FEE_PERCENT.
- Payments: one Payment row per checkout; `services/payments.fulfil()` is the only place that credits money and is
  idempotent. Called from /verify (signature), the webhook (signature + amount) and demo-complete (demo mode only).
- Documents: owner_type job | consultant | service | order; files in document_blobs; read rules in services/access.py
  (open jobs / public profiles / active services visible to signed-in users; orders only to the two parties + admins).
- Every write passes an ownership check; other tenants' records return 404.
- Audit log records sign-ins, registrations, payments, payouts, deletions, plan changes and admin actions.

## History
- v1: FastAPI + single HTML page; matching threshold bug (0.5 vs 50), no re-matching, duplicates.
- v2: fixes, plan limits, tests, vanilla-JS dashboard.
- v3 (this): accounts and roles, marketplace (profiles, services, JDs, proposals, documents), Razorpay payments and
  orders, control room, React frontend, Alembic, Postgres-tested, CI, Render/Vercel/Neon deploy.
- v3.1: automatic freelancer payouts through Razorpay Route (held at payment, released on approval).
- v3.2: global round — reviews & ratings, verified badges, private messaging, in-app + email notifications, password
  reset, countries/timezones/working hours/languages, INR/USD/EUR/GBP with Stripe for non-INR, English/Hindi/Spanish UI,
  hand-built motion set, Vercel /api proxy for first-party cookies.

## v3.2 rules
- Currency: client billing currency defaults from country (IN/unknown→INR, GB→GBP, euro area→EUR, else USD). Jobs default
  to the company currency, services to the freelancer's; orders copy it. Provider per currency in services/payments.py:
  INR→Razorpay (else Stripe), others→Stripe; demo only when no provider is configured at all.
- Route payouts only for INR orders; others become "pending" with a manual-payout reason.
- Messaging: client on a paid plan → anyone; FREE client → freelancers who applied to their jobs or have an order;
  freelancer → clients they applied to / worked with. One conversation per (client, freelancer).
- Notifications: services/notify.notify() stores a row, returns a realtime event (not copied to admins) and emails if
  the user allows it. Message emails only for the first unread message in a thread.
- Reviews: once per party per completed order; rating_avg/rating_count recomputed on Consultant/Client.
- i18n: rendered UI text translated by exact match + patterns; add `translate="no"` around user content.
