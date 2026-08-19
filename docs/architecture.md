# VetLink254 — System Architecture & Engineering Blueprint

**A national veterinary-connect platform: one backend, reachable through both a USSD system and a full website.**

> **READ THIS FIRST: `docs/CURRENT_STATE.md`** is the current, accurate, post-cleanup reference for
> what this repo actually contains and what actually works right now. This file is the original
> product **vision** (the target architecture); the codebase has only built a subset of it so far.
> See also `docs/README.md` for how the docs fit together.

---

## 1. The Core Model — One Backend, Two Front Doors

VetLink254 is built around a single principle: **USSD and the website are two different ways of reaching the exact same system** — not two separate products with separate logic.

- One **Core API / backend** owns every account, clinic, booking, wallet balance, and transaction.
- The **USSD menu** (`*XXX#`) is a thin front door for feature-phone and offline-data users — it does nothing but turn keypresses into calls to the Core API.
- The **website** (and later, a mobile app) is a richer front door for the same backend, giving farmers, clinics, and the veterinary board a fuller interface with maps, dashboards, document upload, and detailed history.
- A booking made via USSD and a booking made via the website land in the exact same database, under the exact same account.
- **Phone number is the universal identity key.** A clinic, vet, or pet owner is a phone number first, an email/website account second. If someone uses USSD today with just a phone number and signs up on the website tomorrow with that same number, their prior activity automatically appears under the new account — because it was never a separate record, it just didn't have a password on it yet.

This is the single most important discipline in the whole system: **the USSD adapter must never contain its own business logic.** All matching, verification, booking, wallet, and payment logic lives in one place and is simply *called* by both front doors.

---

## 2. High-Level Architecture

```
                         ┌─────────────────────────────┐
                         │   Telecom USSD Gateway        │
                         │ (aggregator provider —        │
                         │  covers Safaricom/Airtel/     │
                         │  Telkom via one integration)  │
                         └───────────────┬───────────────┘
                                         │ HTTP webhook per keypress
                                         ▼
        ┌────────────────────────────────────────────────────┐
        │                  API GATEWAY / BFF                  │
        │   (routes: /ussd, /web, /admin, /partner)           │
        └───────┬───────────────┬───────────────┬─────────────┘
                │               │               │
    ┌───────────▼───┐   ┌───────▼────────┐  ┌────▼─────────┐
    │ USSD Service   │   │  Core API       │  │ Admin/Board  │
    │ (session/menu  │   │ (REST/GraphQL)  │  │ API          │
    │  state engine) │   │  — shared logic │  │ (KVB portal) │
    └───────┬────────┘   └───────┬─────────┘  └────┬─────────┘
            │                    │                  │
            └──────────┬─────────┴──────────┬───────┘
                       ▼                    ▼
            ┌─────────────────┐   ┌──────────────────────┐
            │   Domain Services │   │   Shared Data Layer   │
            │ - Matching Engine │   │ - PostgreSQL (core)   │
            │ - Registration/KYC│   │ - Redis (sessions,    │
            │ - Booking Engine  │   │   USSD state, cache)  │
            │ - Payments/Wallet │   │ - S3/Object storage    │
            │ - Notifications   │   │   (docs, certs)        │
            │ - Reporting/BI    │   │ - Analytics warehouse  │
            └─────────┬─────────┘   │   (for KVB dashboards) │
                      │             └──────────────────────┘
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   ┌─────────┐  ┌────────────┐  ┌───────────┐
   │ Payment  │  │ SMS/Email  │  │  Website / │
   │ Gateway  │  │ Gateway    │  │  Web App   │
   │ (mobile  │  │            │  │  (client + │
   │  money   │  │            │  │  clinic +  │
   │  provider)│  │            │  │  admin UI) │
   └─────────┘  └────────────┘  └───────────┘
```

Everything funnels through the same **Core API** and **Domain Services** — USSD, website, mobile (later), and the veterinary board's admin portal are all just different interfaces on one engine.

---

## 3. Core Components Explained

### 3.1 USSD Gateway Layer
A telecom aggregator assigns you a short code (e.g. `*XXX#`). Every keypress a user makes triggers an HTTP POST to your webhook with the session ID, phone number, and text entered so far. Your job is to reply with the next menu screen within a couple of seconds.

### 3.2 USSD Session/Menu Engine
USSD is stateless between keypresses — the telco doesn't remember anything for you between requests. You need a **session state store** (Redis is ideal — fast, expiring keys) tracking: current menu node, choices made so far, phone number, timestamp. The menu itself should be a **navigable tree/config**, not hardcoded if/else chains — this lets you add new menu items without touching core logic.

### 3.3 Core API (Business Logic)
Registration, matching, booking, wallets, and notifications all live here — shared by USSD and the website. Given your Flask background, **FastAPI** is worth strongly considering for this project specifically because of built-in async support (useful for SMS/payment webhooks) and automatic API documentation, which matters once multiple frontends consume the same backend.

### 3.4 Matching Engine (nearest vet/clinic)
Given a farmer's location (GPS from the website, or nearest town/ward selected via USSD menu since USSD has no GPS) and the service needed, this service:
1. Filters registered, **verified**, currently-active clinics/vets offering that service category.
2. Ranks by distance (PostGIS geospatial query if using PostgreSQL — `ST_Distance` on lat/long columns).
3. Falls back by radius tiers (5km → 20km → 50km → "nearest available regardless of distance") so rural areas with sparse coverage still get a match.
4. Excludes clinics whose wallet balance can't cover the lead-response fee (see Section 6), unless you choose to let them accrue debt up to a cap.

### 3.5 Registration & Verification (KYC for clinics/vets)
Documents to require before a clinic/vet goes live on the platform:
- **KVB (Kenya Veterinary Board) practising licence / registration certificate** — non-negotiable given the regulatory nature of veterinary work.
- **Business registration certificate** (or National ID + KRA PIN for a sole practitioner/mobile vet).
- **Proof of premises** (lease/ownership doc) for physical clinics; not required for mobile-only vets.
- **National ID / passport of the responsible veterinary surgeon.**
- **Professional indemnity insurance** (optional at launch, worth capturing if available).
- **A recent passport photo** of the vet, for the public-facing profile/trust signal.
Each submission enters a `pending_verification` state; an admin (or the board, once integrated) approves/rejects with a reason. On approval, the system issues a **unique identity code** (see Section 5).

> **KVB is the licensing authority — VetLink254 is not.** This flow is VetLink254's own *internal
> clinic-onboarding* verification (is this clinic legit to appear on the platform?), NOT a declaration
> of vet licensing status. Whether a **named vet** holds an active KVB licence is always checked
> **live** against KVB's own practitioner-management system (MMS, `mms.kenyavetboard.or.ke`) once it
> exposes a public API; VetLink254 only *caches* that status for the duration of a session and never
> stores it as truth. These are two different concepts and are never merged into one field or endpoint.

### 3.6 Wallet & Payments
> **This is the FARMER→CLINIC payment path** (service payments + lead-response fee) — a separate,
> still-undecided piece, NOT the KVB relationship. VetLink254 does not collect any KVB levy.
> If a KVB-related levy is ever charged it routes through the government's **Pesaflow / eCitizen**
> payment infrastructure and the unified `*222#` USSD gateway under a formal agreement — never a
> private M-Pesa paybill. The wallet/M-Pesa notes below remain the farmer→clinic payment architecture.

Two payment flows exist and should be modeled as genuinely separate ledger entries even though they share infrastructure:
- **Service payments** — a farmer pays for a consultation/treatment/product; VetLink254 collects the payment (via a mobile-money push-payment integration) and disburses to the clinic's payout account minus a platform commission.
- **Lead-response fee** — a small fixed amount deducted from the clinic's *prepaid wallet balance*, not their bank account, the moment they respond to a routed lead. This needs its own wallet table with a transaction log (top-up, deduction, reason, timestamp) — clinics should be able to top up via mobile money and see a running balance in real time.

### 3.7 Notifications
Three channels, one dispatch service: SMS, Email, and in-app/web push. Trigger types: booking confirmed/failed, payment received, reminder (vaccination due, follow-up), board announcements (training, partnership, policy updates broadcast to all registered vets), verification status changes.

### 3.8 Board / National Reporting Layer
This is the piece that makes VetLink254 a national data infrastructure play, not just a booking app. Every interaction (USSD or website) that captures animal type, location (ward/county level, not exact GPS, for privacy), service requested, and outcome should be written to an **analytics-friendly table** (or streamed to a warehouse once volume justifies it) that a board dashboard can query — disease outbreak clustering by region, vaccination coverage gaps, clinic density per county, etc. Keep this **de-identified/aggregated** by default; raw personal data stays in the operational database, not the reporting layer.

---

## 4. Why USSD Needs Different Backend Handling Than the Website

| | USSD | Website |
|---|---|---|
| Identity | Phone number, auto-trusted by telco | Login (password/OTP/Google), phone linked after |
| State | None between requests — you manage it | Standard sessions/JWT |
| Input | Numbered menu choices, free text for names/notes | Full forms, file upload, maps |
| Location | Selected from a list (county → sub-county → ward) | GPS/geolocation API |
| Latency budget | Must respond in ~1-3 seconds per screen | Normal web latency tolerance |
| Payment | Mobile-money push payment triggered from USSD flow, confirmed async via callback | Same, richer UI feedback |

The consequence: your **USSD adapter must be lightweight and fast**, doing almost nothing but reading/writing session state and calling the Core API. Any slow operation (e.g. the matching engine doing a geospatial query across thousands of clinics) needs to be fast enough for a USSD round-trip, or you queue it and send the result via SMS a few seconds later ("We found Dr. Wanjiru, 3km away. Reply 1 to book.").

---

## 5. Identity & Unique Codes

- **Farmer/pet owner ID**: phone number is the primary key. A `users` record is created on first contact (USSD or website) if it doesn't exist. Email/Google login on the website just *attaches* an email + auth method to an existing phone-keyed identity — prompted for during website signup, exactly as you specified.
- **Clinic/Vet ID**: on verification approval, generate a unique code, e.g. `VL254-KVB-00214` (prefix + county code or sequence + zero-padded number). This appears on their public profile, receipts, and is what the matching engine and payment ledger reference — never the raw clinic name, which can change.
- **Booking/Transaction ID**: UUID or a human-readable reference like `VL-20260813-0007F2` for SMS receipts (short, typeable, supports "reply with your booking code" flows).

---

## 6. Data Model (Core Tables)

```
users                  (id, phone[unique], name, email, role[farmer|vet|clinic|admin],
                        created_at, ussd_only_flag)

clinics                 (id, unique_code, owner_user_id, name, county, sub_county,
                        ward, lat, lng, services[], verification_status,
                        wallet_balance, created_at)

verification_documents  (id, clinic_id, doc_type, file_url, status, reviewed_by,
                        reviewed_at)

vets                    (id, clinic_id nullable, user_id, kvb_reg_number,
                        specialization[], is_mobile)

service_categories      (id, name, description)  -- consult, vaccination, mobile visit,
                                                  grooming, boarding, emergency, etc.

bookings                 (id, ref_code, farmer_id, clinic_id, vet_id, service_category_id,
                        animal_type, status[requested|matched|confirmed|completed|
                        cancelled], channel[ussd|web], scheduled_at, created_at)

leads                   (id, booking_id, clinic_id, distance_km, fee_charged,
                        responded_at, response_channel)

wallet_transactions      (id, clinic_id, type[topup|lead_fee|payout], amount,
                        payment_ref, balance_after, created_at)

payments                 (id, booking_id, payer_phone, amount, payment_ref, status,
                        platform_commission, clinic_payout_amount)

notifications            (id, user_id, channel[sms|email|push], type, payload,
                        sent_at, status)

ussd_sessions            (session_id, phone, current_node, context_json, expires_at)
                        -- lives in Redis, not Postgres

board_reports            (id, period, county, metric_type, value, generated_at)
                        -- aggregated, de-identified rollups for the board
```

> **Vet licensing status is never stored in Postgres.** Fields like `vets.kvb_reg_number` are just the
> identifiers used to check status **live** against KVB via the verification bridge (Section 3.5).
> A successful lookup is cached in Redis only for the duration of a USSD session (short TTL) so the
> status is always re-checked per session — KVB, not VetLink254, is the source of truth.

---

## 7. Folder Structure (Monorepo Recommended at This Stage)

A monorepo keeps the "one backend, many front doors" discipline enforced structurally — it's harder to accidentally duplicate logic when the USSD service and the API live side by side and can literally import shared code.

```
vetlink254/
│
├── apps/
│   ├── api/                       # Core API — the single source of truth
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── core/               # cross-cutting: security, db session, settings
│   │   │   │   ├── security.py
│   │   │   │   ├── database.py
│   │   │   │   └── logging.py
│   │   │   ├── models/             # ORM models (SQLAlchemy)
│   │   │   │   ├── user.py
│   │   │   │   ├── clinic.py
│   │   │   │   ├── booking.py
│   │   │   │   ├── payment.py
│   │   │   │   └── wallet.py
│   │   │   ├── schemas/            # request/response schemas
│   │   │   ├── api/                # route definitions, versioned
│   │   │   │   ├── v1/
│   │   │   │   │   ├── users.py
│   │   │   │   │   ├── clinics.py
│   │   │   │   │   ├── bookings.py
│   │   │   │   │   ├── payments.py
│   │   │   │   │   ├── wallet.py
│   │   │   │   │   └── admin.py
│   │   │   ├── services/           # business logic, framework-agnostic
│   │   │   │   ├── matching_engine.py
│   │   │   │   ├── registration_service.py
│   │   │   │   ├── booking_service.py
│   │   │   │   ├── payment_service.py
│   │   │   │   ├── wallet_service.py
│   │   │   │   └── notification_service.py
│   │   │   ├── integrations/       # external providers, isolated behind interfaces
│   │   │   │   ├── payments/
│   │   │   │   │   ├── payment_client.py
│   │   │   │   │   └── callbacks.py
│   │   │   │   ├── sms/
│   │   │   │   │   └── sms_client.py
│   │   │   │   ├── email/
│   │   │   │   │   └── email_client.py
│   │   │   │   └── maps/
│   │   │   │       └── geocoding_client.py
│   │   │   └── workers/            # background jobs (Celery/RQ)
│   │   │       ├── reminder_jobs.py
│   │   │       ├── report_rollup_jobs.py
│   │   │       └── payout_jobs.py
│   │   ├── migrations/
│   │   ├── tests/
│   │   └── requirements.txt
│   │
│   ├── ussd/                       # thin adapter — talks to Core API, owns menu tree only
│   │   ├── app/
│   │   │   ├── main.py             # webhook receiver for the gateway
│   │   │   ├── session_store.py    # Redis-backed session state
│   │   │   ├── menu_tree.py        # declarative menu config (node -> options -> next node)
│   │   │   ├── handlers/
│   │   │   │   ├── farmer_flow.py       # find vet / book / call / advice
│   │   │   │   ├── clinic_registration_flow.py
│   │   │   │   ├── wallet_topup_flow.py
│   │   │   │   └── check_status_flow.py
│   │   │   └── api_client.py       # calls apps/api over HTTP — never touches the DB directly
│   │   └── tests/
│   │
│   ├── web/                        # website — farmer + clinic + public site
│   │   ├── src/
│   │   │   ├── pages/ or app/
│   │   │   │   ├── (public)/       # landing, find-a-vet, about
│   │   │   │   ├── (farmer)/       # bookings, history
│   │   │   │   ├── (clinic)/       # clinic dashboard, wallet top-up, leads inbox
│   │   │   │   └── (admin)/        # board dashboard
│   │   │   ├── components/
│   │   │   ├── lib/api.ts          # typed client for Core API
│   │   │   └── styles/
│   │   └── package.json
│   │
│   └── mobile/                     # optional later phase — same api client pattern
│
├── packages/
│   └── ui/                         # shared design system components (website)
│
├── infra/
│   ├── docker-compose.yml          # local dev: api, ussd, postgres, redis
│   ├── k8s/ or terraform/          # production infra as code
│   └── nginx/ or api-gateway config
│
├── docs/
│   ├── architecture.md             # this document, versioned
│   ├── api-spec.yaml               # auto-generated API spec
│   └── ussd-menu-map.md            # visual map of every USSD screen
│
└── .github/workflows/              # CI/CD — lint, test, deploy per app
```

**Why this shape works for you specifically:** you already have a Flask USSD prototype at roughly 0.5% completion — under this structure, that becomes `apps/ussd/`, and the missing 50%+ is mostly `apps/api/` (the actual business logic) plus wiring the USSD handlers to call it instead of doing their own logic inline, which is almost certainly what the current prototype does.

---

## 8. Tech Stack Recommendation

| Layer | Recommendation | Why |
|---|---|---|
| Core API | **FastAPI** (Python) | You're already comfortable in Python/Flask; FastAPI gives async, auto docs, and validation for free — valuable with multiple consuming frontends |
| USSD adapter | **Flask** (keep it — it's already thin by nature) | No need to rewrite; just strip business logic out of it |
| Database | **PostgreSQL + PostGIS** | Geospatial "nearest clinic" queries are a first-class use case, not an afterthought |
| Session/cache | **Redis** | USSD session state, matching-engine caching, rate limiting |
| Background jobs | **Celery + Redis broker** | Reminders, report rollups, payout batching |
| USSD gateway | A telecom aggregator with broad East African coverage | One integration to reach multiple carriers, plus SMS in the same account |
| Payments | A mobile-money push-payment integration, structured so additional providers can be added later for regional expansion | The FARMER→CLINIC payment path, matching how most East African users actually pay. Any KVB-related levy (if ever introduced) would route via Pesaflow/eCitizen, not a private paybill |
| Website | **Next.js + Tailwind** | Fast to build clinic/farmer/admin dashboards; server-rendering helps the public "find a vet" pages get indexed by search engines, which matters for organic discovery |
| Object storage | **S3-compatible storage** | Verification documents, certificates, photos |
| Analytics/reporting | Start with materialized Postgres views; graduate to a dedicated analytics warehouse once you have real county-level volume for board dashboards | No need to over-engineer this before you have data |
| Hosting | Any (a fast-to-deploy platform for MVP speed; full cloud infra once you need scale + compliance for a govt-facing product) | |

---

## 9. Registration & Booking Flow (End-to-End Example)

**Clinic side:**
1. Clinic owner dials `*XXX#` or visits vetlink254.co.ke → selects "Register my clinic."
2. Provides name, county/ward, service categories, phone.
3. Uploads KVB licence + ID via the website, or — if registration started on USSD — is sent a link/instructions to submit documents through the website (USSD can't handle file uploads).
4. Status: `pending_verification`. Admin/board portal reviews.
5. On approval: unique code issued, SMS/email sent, wallet created at zero balance with a prompt to top up.

**Farmer side:**
1. Dials `*XXX#` → "1. Find a vet near me" → selects animal type → selects service (consult/vaccination/emergency/etc.) → selects location from a ward list (or system uses last known ward if returning user).
2. Matching engine returns top 1–3 clinics; farmer selects one → "Book" or "Call now."
3. If "Call now": the platform bridges the request to the clinic and logs the response; the lead fee is deducted from the clinic's wallet once they actually respond, not simply on being routed the lead.
4. Booking confirmed → SMS sent to both parties → email sent if the farmer has one on file → reminder scheduled.
5. On completion, payment (if applicable) is collected via mobile-money push payment, split between clinic payout and platform commission, and a receipt emailed/SMS'd.

---

## 10. Build Order (Practical Next Steps)

1. **Stand up `apps/api` first**, even skeletal — models for `users`, `clinics`, `bookings`, and one endpoint each. This is the piece everything else depends on.
2. **Rebuild `apps/ussd` as a pure adapter** against that API — this is where your existing Flask code gets refactored, not thrown away.
3. **Matching engine** with a hardcoded small dataset (a handful of test clinics with lat/long) before worrying about scale.
4. **Mobile-money integration** for wallet top-up — get this working early since it unlocks the whole monetization loop.
5. **Website dashboard** for clinics (leads inbox, wallet) — this is what makes the platform legible to a real clinic owner testing it.
6. **Admin/board reporting layer** last — it needs real usage data to be meaningful, and it's the piece you'll want to demo once you have Phase 1 (PetCare as flagship clinic) live and generating data.

---

*This document is meant to live alongside the pitch deck as the engineering companion — the deck sells the vision, this defines how it actually gets built.*
