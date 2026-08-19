# VetLink254 — CURRENT STATE (read this FIRST)

> **This is the authoritative, up-to-date reference for the repo as it exists right now.**
> A brand-new agent or developer should read **this file first**, then
> `docs/architecture.md` for the original product vision, then
> `docs/progress/LOG.md` / `docs/progress/STATUS.md` for session-by-session history.
>
> Last updated: 2026-08-20 (DEMO-READINESS PASS: Render blueprint written but NOT deployed; minimal single-admin JWT auth replacing the shared admin token; KYC file upload with R2 code-complete + live local-disk fallback; public verified-clinics web dashboard; CI workflow; clean isolated git history pushed + tagged v0.1.0-demo). Prior: 2026-08-18 (USSD nav rework: context-dependent "0"/"00" home-vs-end, unrestricted county search + shared continuous pagination via "98", optional sub-location with "9 to skip"; SMS switched to the official africastalking SDK with KYC/board wiring; docs/KVB_INTEGRATION.md added). Prior: 2026-08-16 (47-county search, ~24-service paginated catalogue, EN/SW bilingual, SMS notifications); real KVB integration is stub-only and externally blocked.
> Every command in this file was re-verified live against the running stack on 2026-08-14, and the demo-readiness changes (JWT auth, multipart upload, dashboard, USSD end-to-end) were re-verified live on 2026-08-20 (see the 2026-08-20 LOG.md entry for the full walkthrough transcript and the test runs).

---

## 0. One-paragraph orientation

VetLink254 is a national veterinary-connect platform with **one backend** (a FastAPI Core API,
`apps/api`) reached through **two front doors**: a thin **USSD adapter** (`apps/ussd`, Flask) for
feature-phone users and a **website** (`apps/web`, **built 2026-08-20** — a plain HTML/CSS/JS
public verified-clinics dashboard, no framework, no build step). The core
discipline (architecture.md §1): the USSD adapter contains **no business logic** — it walks a menu
tree, stores session state in Redis, and delegates all matching to the Core API over HTTP.

**What exists and works today:** a Core API serving users / clinics / bookings / KYC documents
(multipart file upload, verified on 2026-08-20) / admin-verify (single-admin JWT auth, verified on
2026-08-20) / nearest-clinic matching / live KVB vet-license lookup, a USSD adapter that walks a
real "find a vet" flow **and** a "verify a vet" flow, a public verified-clinics web dashboard, a
docker-compose stack (api :8000, ussd :8001, web :8002, postgres, redis), a Render blueprint
(config only — **NOT yet deployed**), and a CI workflow.
**What does not exist yet (or is not live):** full authentication (roles/OTP/refresh — the 2026-08-20
pass delivered a deliberate single-admin MVP only), wallet/payments, telecom gateway integration
(no short code, no public HTTPS webhook; `/simulate` + `POST /ussd` sandbox only), real SMS
(Africa's Talking SDK wired but **STUB/no-op** until `AT_USERNAME` + `AT_API_KEY` are set), real
R2 object storage (code-complete, **pending R2 credentials** — the local-disk fallback at `/uploads`
is what works tonight), the board/reporting layer — and **real KVB integration** (the license
bridge runs against a temporary STUB; the real KVB API is externally blocked, see §5.12).

---

## 1. The real folder tree (generated live from the filesystem after the 2026-08-14 cleanup)

```
VetLink254 Software/
│
├── .gitignore                                # ignores __pycache__/, *.pyc, .env, .venv, node_modules, local db, uploads
├── AGENT_PROTOCOL.md                         # build protocol + logging rules every agent must follow
├── README.md                                 # root README (added 2026-08-20) — what this is + quick start
├── render.yaml                               # Render Blueprint — DEPLOYMENT CONFIG ONLY, NOT YET DEPLOYED
├── run_tests.sh                              # runs both pytest suites in throwaway python:3.11-slim containers
├── .github/workflows/ci.yml                  # CI: ./run_tests.sh + docker build of api/ussd/web (2026-08-20)
│
├── apps/                                     # every application/front-door lives here (monorepo)
│   │
│   ├── api/                                  # Core API — the single source of truth (FastAPI)
│   │   ├── .env.example                      # env template for the api service (also read by docker-compose)
│   │   ├── Dockerfile                        # builds vetlink_api container (python:3.11-slim + uvicorn :8000)
│   │   ├── README.md                         # short per-app quick start
│   │   ├── requirements.txt                  # pinned deps: fastapi, uvicorn, sqlalchemy, alembic, psycopg2, pydantic, bcrypt, PyJWT, boto3, python-multipart...
│   │   ├── alembic.ini                       # Alembic config (script_location=alembic, prepend_sys_path=.)
│   │   ├── alembic/                          # database migrations
│   │   │   ├── env.py                        # wires alembic to DATABASE_URL + app models metadata
│   │   │   ├── script.py.mako                # migration template (standard alembic)
│   │   │   └── versions/
│   │   │       ├── 001_initial_migration.py  # creates users, clinics, bookings tables
│   │   │       ├── 002_verification_kyc.py   # creates verification_documents + clinic verification columns
│   │   │       ├── 003_verification_contact_phone.py  # adds verification_documents.contact_phone
│   │   │       └── 004_admin_auth.py         # adds users.password_hash (2026-08-20) — head
│   │   ├── scripts/
│   │   │   └── create_admin.py               # idempotent env-var admin seeding (run by api start + Render release)
│   │   └── app/
│   │       ├── __init__.py                   # package marker
│   │       ├── main.py                       # FastAPI entrypoint: /health + all v1 routers + CORS + /uploads static + auth router; NO create_all (Alembic is sole schema mechanism)
│   │       ├── config.py                     # Pydantic Settings (DATABASE_URL, REDIS_URL, ADMIN_EMAIL/ADMIN_PASSWORD, SECRET_KEY, CORS_ORIGINS, R2_*, LOCAL_UPLOAD_DIR, DOC_UPLOAD_MAX_MB, ...)
│   │       ├── api/                          # route definitions
│   │       │   ├── __init__.py               # package marker
│   │       │   └── v1/
│   │       │       ├── __init__.py           # package marker
│   │       │       ├── users.py              # GET/POST /api/v1/users
│   │       │       ├── clinics.py            # GET list / GET one / POST create / PATCH update (PATCH needs JWT)
│   │       │       ├── bookings.py           # GET/POST /api/v1/bookings
│   │       │       ├── verification.py       # multipart POST + GET /clinics/{id}/documents, POST /clinics/{id}/verify (needs JWT)
│   │       │       ├── auth.py               # POST /api/v1/auth/login -> HS256 Bearer JWT (2026-08-20)
│   │       │       ├── match.py              # GET /api/v1/match?lat&lng&service&limit — nearest verified clinics
│   │       │       ├── kvb.py                # GET /api/v1/verify-license?license_number= — live KVB vet-license lookup (STUB)
│   │       │       └── notify.py             # POST /api/v1/notify — SMS dispatch for USSD (farmer SMS + board stopgap)
│   │       ├── core/                         # cross-cutting infrastructure
│   │       │   ├── __init__.py               # package marker
│   │       │   ├── database.py               # SQLAlchemy engine + session + Base (reads DATABASE_URL)
│   │       │   └── security.py               # bcrypt hash/verify + PyJWT HS256 create/decode + get_current_admin + ensure_admin_user (2026-08-20; replaces the X-Admin-Token stopgap)
│   │       ├── integrations/                 # external providers, isolated behind clean interfaces
│   │       │   ├── __init__.py               # package marker
│   │       │   ├── kvb_client.py             # KVBVerificationClient — STUB-first KVB license bridge (OAuth2 + per-session Redis cache)
│   │       │   ├── sms_client.py             # SMSClient — Africa's Talking SMS (STUB/no-op when AT creds unset; never crashes the flow)
│   │       │   └── storage_client.py         # StorageClient: R2StorageClient (boto3) + LocalStorageClient fallback, MIME allowlist, 10MB cap (2026-08-20)
│   │       ├── models/                       # SQLAlchemy ORM models
│   │       │   ├── __init__.py               # exports User, Clinic, Booking, VerificationDocument
│   │       │   ├── user.py                   # users table (phone = universal identity key; + password_hash 2026-08-20)
│   │       │   ├── clinic.py                 # clinics table (location, services JSON, verification fields, wallet_balance)
│   │       │   ├── booking.py                # bookings table
│   │       │   └── verification_document.py  # verification_documents table (KYC docs; file_url = object URL/local /uploads path)
│   │       ├── schemas/                      # Pydantic request/response schemas
│   │       │   ├── __init__.py               # re-exports all schemas for convenience imports
│   │       │   ├── user.py                   # UserCreate / UserResponse
│   │       │   ├── clinic.py                 # ClinicCreate / ClinicUpdate / ClinicResponse
│   │       │   ├── booking.py                # BookingCreate / BookingResponse
│   │       │   ├── verification.py           # VerificationDecision / VerificationResponse (VerificationDocumentCreate removed 2026-08-20)
│   │       │   ├── auth.py                   # AuthLogin / TokenResponse (2026-08-20)
│   │       │   ├── match.py                  # MatchResult (ClinicResponse + computed distance_km)
│   │       │   └── kvb.py                    # VetVerificationResult (status/name/license_type/checked_at)
│   │       └── services/                     # framework-agnostic business logic
│   │           ├── __init__.py               # package marker
│   │           ├── matching_engine.py        # haversine_km() + find_nearest_clinics() — Haversine, not PostGIS
│   │           └── registration_service.py   # approve/reject clinic + VL254-<CC>-<seq> unique code generator
│   │
│   ├── ussd/                                 # thin USSD adapter — holds NO business logic (Flask)
│   │   ├── .env.example                      # env template for the ussd service
│   │   ├── Dockerfile                        # builds vetlink_ussd container (gunicorn :8001)
│   │   ├── README.md                         # build/simulate instructions
│   │   ├── requirements.txt                  # pinned deps: flask, flask-cors, redis, requests, gunicorn
│   │   └── app/
│   │       ├── __init__.py                   # package marker
│   │       ├── main.py                       # POST /ussd webhook + GET/POST /simulate sandbox + GET /health
│   │       ├── session_store.py              # Redis-backed session state (180s TTL, no in-memory fallback)
│   │       ├── menu_tree.py                  # declarative menu tree (language→find-a-vet + verify-a-vet), 47-county type-to-search, ~24-service catalogue w/ continuous numbering ("98"=next page), TRANSLATIONS EN/SW
│   │       └── api_client.py                 # thin HTTP client calling apps/api (GET /match, GET /verify-license, POST /notify) — never touches DB/SMS
│   │
│   └── web/                                  # public verified-clinics dashboard (2026-08-20) — plain HTML/CSS/JS, no build step
│       ├── index.html                        # window.VETLINK_API_BASE (default http://localhost:8000) + structure
│       ├── style.css                         # styling
│       ├── app.js                            # fetches GET /api/v1/clinics/, filters verification_status=="verified", renders cards
│       ├── Dockerfile                        # python http.server on :8002 (serve-static)
│       └── README.md                         # what it is + how to point it at a real api URL
│
├── docker-compose.yml                        # local dev orchestration: api(:8000), ussd(:8001), web(:8002), postgres, redis
│
└── docs/
    ├── CURRENT_STATE.md                      # ← YOU ARE HERE: comprehensive, current reference
    ├── architecture.md                       # original product vision / engineering blueprint (sections still referenced by LOG.md)
    └── progress/
        ├── LOG.md                            # session-by-session build history (running log, append-only)
        └── STATUS.md                         # living snapshot: what's built / next / broken (updated each session)
```

---

## 2. What Actually Works Right Now

Every feature below was re-verified **live against the running docker-compose stack** on 2026-08-14.
The four containers (`vetlink_api`, `vetlink_ussd`, `vetlink_postgres`, `vetlink_redis`) were all up.

### 2.1 The docker-compose stack itself
- **How to start:** from the repo root, `docker compose up --build -d`.
- **How to check it's up:** `docker compose ps` — expect `vetlink_api`, `vetlink_ussd`, `vetlink_web`, `vetlink_postgres`, `vetlink_redis` all `Up`.
- **Ports:** api → `http://localhost:8000`, ussd → `http://localhost:8001`, web → `http://localhost:8002`, postgres → `5432`, redis → `6379`.
- **Dependencies:** api needs postgres + redis (declared via `depends_on`); ussd needs api + redis; web is a static site (no deps).
- **Important gotcha:** uvicorn and gunicorn run **without `--reload`**, so code edits (which are
  volume-mounted) require `docker restart vetlink_api` (and/or `docker restart vetlink_ussd`) to take effect — **not** a rebuild.
- **Admin seed:** the api start command runs `alembic upgrade head && python -m scripts.create_admin` automatically, so the admin account from `ADMIN_EMAIL`/`ADMIN_PASSWORD` (dev default `admin@vetlink254.local` / `dev-admin-password-change-me`) exists on first boot.

### 2.2 Core API health check
- **URL:** `GET http://localhost:8000/health`
- **Verify:** `curl -s http://localhost:8000/health` → `{"status":"ok"}`
- **Depends on:** postgres (DB engine created lazily on first request) + redis is *not* touched by the api at all yet.

### 2.3 Users (basic CRUD, no auth)
- **Endpoints:** `GET /api/v1/users/`, `POST /api/v1/users/`
- **Verify:**
  ```bash
  curl -s -X POST http://localhost:8000/api/v1/users/ -H "Content-Type: application/json" \
    -d '{"phone":"+254700000001","name":"Test Farmer","role":"farmer"}'
  curl -s http://localhost:8000/api/v1/users/
  ```
- **Depends on:** postgres. **No auth.**

### 2.4 Clinics (basic CRUD + location update)
- **Endpoints:** `GET /api/v1/clinics/`, `GET /api/v1/clinics/{id}`, `POST /api/v1/clinics/`, `PATCH /api/v1/clinics/{id}`
- **Verify:**
  ```bash
  curl -s http://localhost:8000/api/v1/clinics/
  curl -s http://localhost:8000/api/v1/clinics/2
  curl -s -X POST http://localhost:8000/api/v1/clinics/ -H "Content-Type: application/json" \
    -d '{"name":"New Clinic","county":"Nairobi","verifying_authority":"KVB-KE"}'
  # PATCH requires a login (see §2.7 for how to get a JWT):
  curl -s -X PATCH http://localhost:8000/api/v1/clinics/2 -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" -d '{"lat":-1.2833,"lng":36.8167}'
  ```
- **Depends on:** postgres. GET/POST are open; **PATCH requires a Bearer JWT**.

### 2.5 Bookings (basic CRUD, no business logic)
- **Endpoints:** `GET /api/v1/bookings/`, `POST /api/v1/bookings/`
- **Verify:**
  ```bash
  curl -s http://localhost:8000/api/v1/bookings/
  curl -s -X POST http://localhost:8000/api/v1/bookings/ -H "Content-Type: application/json" \
    -d '{"ref_code":"VL-20260814-0001","farmer_id":1,"animal_type":"Dog"}'
  ```
- **Depends on:** postgres (farmer_id must reference an existing user). **No auth.**

### 2.6 Registration & Verification (KYC) — clinic goes live
- **Endpoints:**
  - `POST /api/v1/clinics/{id}/documents` (MULTIPART file upload: `file`, `doc_type`, optional `contact_phone`; open)
  - `GET /api/v1/clinics/{id}/documents` (list docs; open)
  - `POST /api/v1/clinics/{id}/verify` (approve/reject; **requires Bearer JWT**)
- **Document upload rules (2026-08-20):** allowed MIME types = `image/png`, `image/jpeg`, `image/webp`, `application/pdf` (else **415**); max size = `DOC_UPLOAD_MAX_MB` (default 10) (**413**); empty file → **400**. With `R2_*` env vars set the bytes go to Cloudflare R2; otherwise they are written under `LOCAL_UPLOAD_DIR/kyc/<uuid>/<file>` and served back at `/uploads/...` (the object URL / local path is stored in the existing `file_url` column).
- **Verify (full register → verify flow, re-verified live 2026-08-20 with JWT + real multipart PDF):**
  ```bash
  # 0. get a JWT (see §2.7)
  TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" \
    -d '{"email":"admin@vetlink254.local","password":"dev-admin-password-change-me"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

  # 1. create the clinic (open)
  curl -s -X POST http://localhost:8000/api/v1/clinics/ -H "Content-Type: application/json" \
    -d '{"name":"KYC Test Clinic","county":"Nairobi","verifying_authority":"KVB-KE"}'
  # 2. submit a license document (open, multipart) -> flips status to pending_verification
  curl -s -X POST http://localhost:8000/api/v1/clinics/5/documents \
    -F "file=@/tmp/licence.pdf" -F "doc_type=license" -F "contact_phone=+254712345678"
  # 3. approve WITHOUT token -> 401
  curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/v1/clinics/5/verify \
    -H "Content-Type: application/json" -d '{"decision":"approved","reviewed_by":"admin@vetlink254"}'
  # 4. approve WITH JWT -> verified + unique_code issued (e.g. VL254-KE-00003)
  curl -s -X POST http://localhost:8000/api/v1/clinics/5/verify -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" -d '{"decision":"approved","reviewed_by":"admin@vetlink254","reason":"docs valid"}'
  # 5. confirm status + code
  curl -s http://localhost:8000/api/v1/clinics/5
  ```
- **Behavior:** approve → `verification_status=verified` + issues `VL254-<2-letter region>-<5-digit seq>`
  (region derived from `verifying_authority`, e.g. `KVB-KE` → `KE`). Reject → `rejected` + stores reason in `verification_note`.
- **Depends on:** postgres (+ local disk when R2 unset). Verify is the admin action (JWT).

### 2.7 Minimal JWT auth (single admin) — replaces the old shared-token stopgap
- **What it is:** one admin user seeded idempotently from `ADMIN_EMAIL`/`ADMIN_PASSWORD` env vars
  (`apps/api/scripts/create_admin.py`, run automatically by the api start/release commands) with a
  bcrypt hash in `users.password_hash`. `POST /api/v1/auth/login` returns an **HS256 Bearer JWT**
  (`SECRET_KEY`, expiry `ACCESS_TOKEN_EXPIRE_MINUTES` default 1440). Exactly two endpoints require it:
  `POST /clinics/{id}/verify` and `PATCH /clinics/{id}` (missing/bad token → **401**, non-admin role → **403**).
- **Verify (live-tested 2026-08-20):**
  ```bash
  # login -> {"access_token": "...", "token_type": "bearer", "expires_in_minutes": 1440}
  TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" \
    -d '{"email":"admin@vetlink254.local","password":"dev-admin-password-change-me"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
  curl -i -X PATCH http://localhost:8000/api/v1/clinics/5 -H "Content-Type: application/json" -d '{"lat":-1.2663}'  # 401 without
  curl -i -X PATCH http://localhost:8000/api/v1/clinics/5 -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"lat":-1.2663}'  # 200 with
  ```
- **This is a DELIBERATE MVP, not the full auth system** — single admin role, no refresh tokens, no
  OTP, no login UI, no rate limiting (see §5.1). The old `X-Admin-Token` / `ADMIN_API_TOKEN` mechanism is **gone**.

### 2.8 Matching Engine (nearest verified clinic)
- **Endpoint:** `GET /api/v1/match?lat=<float>&lng=<float>&service=<str>&limit=<1..20, default 3>`
- **Logic (in `apps/api/app/services/matching_engine.py`):** only clinics with
  `verification_status=="verified"` are considered; the requested `service` must appear in the
  clinic's `services` JSON list (case-insensitive); clinics without lat/lng are excluded; distance is
  computed with the **Haversine formula in plain Python** (PostGIS is a planned future optimization).
- **Verify (live-tested):**
  ```bash
  # clinic 2 "PetCare Global Clinic" (lat -1.2833, lng 36.8167) matched from downtown Nairobi
  curl -s "http://localhost:8000/api/v1/match/?lat=-1.2921&lng=36.8219&service=consultation"
  # -> returns clinic 2 with distance_km ~1.137

  # case-insensitive service match
  curl -s "http://localhost:8000/api/v1/match/?lat=-1.2921&lng=36.8219&service=VACCINATION"

  # empty result (not an error) for a service nobody offers
  curl -s "http://localhost:8000/api/v1/match/?lat=-1.2921&lng=36.8219&service=grooming"   # -> []

  # limit honored
  curl -s "http://localhost:8000/api/v1/match/?lat=-1.2921&lng=36.8219&service=consultation&limit=1"
  ```
- **Depends on:** postgres. **No auth** (public by design).

### 2.9 USSD thin adapter — full "Find a vet" walkthrough
- **Endpoints:** `POST /ussd` (real gateway webhook format: `sessionId`, `phoneNumber`, `text`),
  `GET|POST /simulate` (local Africa's Talking-style sandbox), `GET /health`.
- **How to start:** it is part of the compose stack (port `8001`). Health:
  ```bash
  curl -s http://localhost:8001/health   # -> {"redis":"connected","status":"ok"}
  ```
- **Verify — full menu walk (English, Consultation from Nairobi), same `session_id`, accumulating `text` joined with `*`:**
  ```bash
  curl -s "http://localhost:8001/simulate?session_id=demo1&text="            # CON Chagua lugha / Choose language (1. English 2. Kiswahili)
  curl -s "http://localhost:8001/simulate?session_id=demo1&text=1"           # CON Welcome to VetLink254 (Home) (1. Find a vet, 2. Verify a vet; footer "00. End")
  curl -s "http://localhost:8001/simulate?session_id=demo1&text=1*1"         # CON animal type
  curl -s "http://localhost:8001/simulate?session_id=demo1&text=1*1*1"       # CON service (Page 1/3; "98" = More options)
  curl -s "http://localhost:8001/simulate?session_id=demo1&text=1*1*1*98"    # CON service Page 2/3 (items 10-18 — continuous numbering)
  curl -s "http://localhost:8001/simulate?session_id=demo1&text=1*1*1*98*98" # CON service Page 3/3 (19-24 + "25. Type a service not listed")
  curl -s "http://localhost:8001/simulate?session_id=demo1&text=1*1*1*98*98*25"     # CON free-text custom-service prompt
  curl -s "http://localhost:8001/simulate?session_id=demo1&text=1*1*1*98*98*25*Pet grooming"  # CON "Type part of your county name"
  curl -s "http://localhost:8001/simulate?session_id=demo1&text=1*1*1*98*98*25*Pet grooming*nai"   # CON "Counties matching: 1. Nairobi"
  curl -s "http://localhost:8001/simulate?session_id=demo1&text=1*1*1*98*98*25*Pet grooming*nai*1" # CON "Type your area, or reply 9 to skip: (9. Skip)"
  curl -s "http://localhost:8001/simulate?session_id=demo1&text=1*1*1*98*98*25*Pet grooming*nai*1*9"  # CON results (clinics + distance_km) — sub-location skipped
  curl -s "http://localhost:8001/simulate?session_id=demo1&text=1*1*1*98*98*25*Pet grooming*nai*1*9*1" # END clinic details
  ```
  Kiswahili: start with `text=2` and every screen renders in SW (incl. "00. Nyumbani" home footer).
- **Verify — context-dependent "00"/"000" nav:**
  ```bash
  curl -s "http://localhost:8001/simulate?session_id=demo2&text=1*1*00"  # CON Welcome again — session STAYS ALIVE, flow context reset, language kept
  curl -s "http://localhost:8001/simulate?session_id=demo2&text=00"      # END goodbye + session deleted (now ON the welcome/home screen)
  ```
- **Verify — real gateway webhook format:**
  ```bash
  curl -s -X POST http://localhost:8001/ussd -d "sessionId=gw1&phoneNumber=%2B254712345678&text=1*1*1*1"
  ```
- **Verify — session lifecycle in Redis:**
  ```bash
  docker exec vetlink_redis redis-cli GET "ussd:session:demo1"    # node + context JSON while mid-flow
  docker exec vetlink_redis redis-cli EXISTS "ussd:session:demo1" # 0 after an END screen or "00" on Home
  ```
- **Dependencies:** apps/api (via `API_BASE_URL` → `GET /api/v1/match`) and Redis (session state).
  The USSD container has **no database env and no psycopg2/sqlalchemy** — it physically cannot touch Postgres.
- **CORS:** `/simulate` and `/ussd` allow all origins (dev-only) — see §5.

### 2.10 Auto-generated API docs
- **URL:** `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc` (ReDoc) — FastAPI built-in.

### 2.11 Automated tests (pytest — apps/api + apps/ussd)
- **What exists:** an automated pytest suite covering `apps/api` (138 tests, ~96% coverage of `app/`) and
  `apps/ussd` (73 tests). On 2026-08-20 the API suite grew from 114 to 138 with the new auth + storage
  coverage (login success/failure, 401/403 matrix on verify+PATCH, multipart upload accept/415/413,
  R2 via a fake boto3 client, local-disk uploads). No business logic regressions were introduced; all
  138 + 73 green via a local Python 3.14 venv (Docker was unavailable that session — see §5.8).
- **Run everything with one command (no docker-compose, no Postgres, no Redis needed):**
  ```bash
  ./run_tests.sh        # from the repo root
  ```
  It runs each suite in a throwaway `python:3.11-slim` container (the same Python version as the
  production Dockerfiles) and installs the pinned `requirements.txt` inside, so it works on any
  machine with Docker. Each app spins up its **own isolated test fixtures** (SQLite for the API;
  in-memory session store + mocked `api_client` for USSD). The CI workflow (`.github/workflows/ci.yml`)
  runs exactly this, plus a `docker build` of the api/ussd/web images.
- **apps/api alone** (from `apps/api/`):
  ```bash
  docker run --rm -v "$PWD":/app -w /app \
    -e COVERAGE_FILE=/tmp/.coverage -e PYTHONDONTWRITEBYTECODE=1 \
    python:3.11-slim sh -c \
    "pip install --quiet -r requirements.txt && python -m pytest tests/ -p no:cacheprovider --cov=app --cov-report=term-missing"
  ```
- **apps/ussd alone** (from `apps/ussd/`):
  ```bash
  docker run --rm -v "$PWD":/app -w /app -e PYTHONDONTWRITEBYTECODE=1 \
    python:3.11-slim sh -c \
    "pip install --quiet -r requirements.txt && python -m pytest tests/ -p no:cacheprovider"
  ```
- **How the tests isolate themselves:**
  - `apps/api/tests/conftest.py` overrides `DATABASE_URL` to a temp file-based **SQLite** DB *before* the
    app is imported (no Postgres server), and sets `ADMIN_EMAIL`/`ADMIN_PASSWORD`/`LOCAL_UPLOAD_DIR`
    (temp dir) so the seeded admin + real local-disk uploads work in tests. SQLAlchemy JSON columns work
    on SQLite (stored as TEXT); the only behavioral difference that matters here is tz-aware datetimes
    coming back naive — harmless for these tests. Every table is emptied before each test so tests never
    share state. Choice rationale and the Postgres differences are logged in `docs/progress/LOG.md`.
  - `apps/ussd/tests/` uses an in-memory session-store stand-in for the full flow, tests the real
    `RedisSessionStore` against `fakeredis`, and mocks `api_client.match_clinics` — no Redis server, no
    live call to apps/api.
- **What's covered:** matching engine (Haversine vs known distances — 1° lat ≈ 111.195 km,
  London→Paris ≈ 343.5 km, the live downtown-Nairobi→PetCare fixture ≈ 1.137 km; verified-only filter;
  case-insensitive services; null/empty-services and missing-coordinates exclusions; distance ordering;
  limit; empty result), registration service (`VL254-<CC>-<seq>` format, region derivation incl. "XX"
  fallback, approve/reject), and every HTTP endpoint via FastAPI `TestClient` (clinics CRUD + **JWT**
  auth on verify/PATCH — 401 without/bad token, 200 with, 403 non-admin; auth/login incl. wrong
  password + unknown email + 422 + 403; verification/documents multipart upload + list; match endpoint;
  users; bookings; **storage client** — MIME allowlist, size cap, LocalStorageClient real writes +
  unique keys + sanitised basename, R2 via fake boto3 client + failure→`StorageError`, `r2_configured`
  selection). KVB bridge: `KVBVerificationClient` stub mode (active/expired/not-found + stub WARNING
  log), the per-session Redis cache (hit, TTL=0 disable, Redis-failure degradation), the real-mode
  OAuth2 HTTP path via `httpx.MockTransport`, and the `GET /api/v1/verify-license` endpoint
  (active/expired/404/422/502, no-admin-token-needed). SMS: SDK-backed client (stub no-op + fake-SDK
  live path), notify dispatch, KYC SMS wiring, verify-license board SMS. USSD: menu-tree structure and
  option resolution, `RedisSessionStore` roundtrip/TTL/delete/corrupt-payload, the full find-a-vet flow
  (results, no-match, api-down, back-nav, "00", invalid choice), and the full verify-a-vet flow
  (welcome option, license prompt, active / expired / not-found / api-down END screens, back-nav,
  session cleared on END).
- **Known gaps:** CI exists but its green-on-GitHub run is pending the first push; no docker-compose
  integration test; and the USSD suite still does not exercise the Flask HTTP routes (`/ussd`,
  `/simulate`, `/health`, CORS) at the HTTP layer (the 2026-08-20 live walkthrough exercised them via a
  local harness with fakeredis instead).

### 2.12 KVB vet-license verification — "Verify a vet" (API + USSD, **STUB ONLY**)
- **What this is:** a B2C bridge so a farmer can check a vet's license status. VetLink254 is **NOT**
  the authority on who is licensed — KVB is. `GET /api/v1/verify-license` calls OUT to KVB
  (via `apps/api/app/integrations/kvb_client.py`, OAuth2 client-credentials) and **never stores the
  result in Postgres** — successful lookups are cached in Redis for 180s only (matching the USSD
  session TTL), so status is always re-checked live per session.
- **⚠️ STUB MODE (IMPORTANT):** KVB does not yet expose a public API, so the client ships in a
  **temporary stub mode** (`KVB_API_BASE_URL` unset or `"stub"`). It returns canned data for a few
  fake license numbers and logs a **WARNING on every call** so it can never be mistaken for a real
  integration. Everything below runs against the **STUB** — it is NOT real KVB data. Swapping in the
  real endpoint is a drop-in change (§7.11).
- **Fake stub numbers:** `KVB-1001` / `KVB-1002` (active), `KVB-1003` (expired), anything else (not found).
- **Endpoints:**
  - `GET /api/v1/verify-license?license_number=<str>` → `{"status","name","license_type","checked_at"}`
  - Public by design (farmer-facing lookup) — **no admin token needed** (decision logged).
- **Verify:**
  ```bash
  # active vet
  curl -s "http://localhost:8000/api/v1/verify-license?license_number=KVB-1001"
  # -> {"status":"active","name":"Dr. Wanjiku Kamau","license_type":"Veterinary Surgeon","checked_at":"..."}

  # expired license (not verified)
  curl -s "http://localhost:8000/api/v1/verify-license?license_number=KVB-1003"

  # unknown number -> HTTP 404 "No vet found..."
  curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8000/api/v1/verify-license?license_number=KVB-9999"
  ```
- **USSD "Verify a vet" walkthrough** (new menu branch, second option on the Welcome screen):
  ```bash
  curl -s "http://localhost:8001/simulate?session_id=verify1&text="           # CON Chagua lugha / Choose language
  curl -s "http://localhost:8001/simulate?session_id=verify1&text=1"          # CON Welcome (1. Find a vet, 2. Verify a vet)
  curl -s "http://localhost:8001/simulate?session_id=verify1&text=1*2"        # CON "Enter the vet's KVB license number:" (free text)
  curl -s "http://localhost:8001/simulate?session_id=verify1&text=1*2*KVB-1001"  # END "Dr. Wanjiku Kamau is a VERIFIED KVB Veterinary Surgeon."
  ```
  A successful lookup also triggers `POST /api/v1/notify` (event "verify") → farmer SMS + board stopgap SMS.
  Not-found → END "No vet is registered with KVB license number ...". Inactive/expired → END "... NOT currently verified".
  api/KVB failure → END "Service temporarily unavailable. Please try again shortly." (same pattern as find-a-vet).
- **Design notes:** the USSD adapter stays thin — it only forwards the license number to the API and
  renders the answer; no licensing logic lives in the USSD app. Free-text input is handled
  declaratively (`free_text=True` on the `verify_license` node in `menu_tree.py`), not hardcoded
  if/else in `main.py`.
- **Distinct from clinic onboarding:** this is a *named vet's live KVB license status*. It is NOT the
  internal clinic KYC verification (`verifying_authority` / `POST /clinics/{id}/verify`) — a clinic
  being "verified" on VetLink254 is a different concept from a vet holding an active KVB license.
  The two are never merged into one field or endpoint.

### 2.13 National USSD + bilingual + SMS notifications (2026-08-16)
- **Language first:** the very first USSD screen is `Chagua lugha / Choose language` → `1. English
  2. Kiswahili`; the choice is stored in session context (`context["language"]`) and drives every
  prompt/label for that session via the `TRANSLATIONS` dict in `apps/ussd/app/menu_tree.py`
  (English canonical; Kiswahili best-effort, technical terms flagged `TODO-SW` for native review).
- **47-county location search — USSD-native type-to-search, NO GPS (hard constraint):** the farmer
  types **1 letter to the full county name** (no fixed length limit) → case-insensitive substring
  filter → numbered matches; **zero matches → clear retry message staying on the node**; **more than
  9 matches paginate** with the SAME continuous-numbering pattern as services (`98` = next page,
  numbers keep counting across pages). Each county carries an **approximate centroid lat/lng**
  (documented limitation: no geocoding infrastructure / no paid key), used purely as the `lat`/`lng`
  args for `GET /api/v1/match`. After picking a county, the farmer may type a free-text
  **sub-location/area** (e.g. "Kilimani", "Ruiru town") stored as TEXT on context and **not
  geocoded**, OR reply **"9" to skip** (a real menu option — nothing stored when skipped). Matching
  uses the county centroid until real geocoding is built (logged approximation, not a bug).
- **~24-service catalogue with CONTINUOUS numbering across pages:** page 1 = 1-9, page 2 = 10-18,
  page 3 = 19-24 + **"25. Type a service not listed"** free-text custom-service entry (stored
  verbatim and flagged `context["custom_service"]=True` — uncatalogued, flagged for later review).
  Reserved next-page key **"98"** must never collide with an item number (design rule: keep totals
  < 90; currently 24 services + 47 counties). "0. Back" and "00. Home" footers; "00. End" appears
  ONLY on the welcome/home screen. Canonical service values are matched case-insensitively against
  clinic `services`; the Clinic model is unchanged.
- **"0"/"00" navigation (Part 1 rework):** "0" = Back (shown only when a screen has a back target);
  **"00"/"000" is context-dependent** — on the **Welcome/Home screen it ENDS the session** (session
  deleted), on **any other screen it jumps straight home WITHOUT ending the session**, resetting
  in-progress selections but keeping `context["language"]`.
- **SMS notifications (Africa's Talking) — official SDK, STUB/no-op until creds are set:**
  - `apps/api/app/integrations/sms_client.py` uses the **official `africastalking` SDK (pinned
    2.0.3)**; `SMSClient.send_sms(phone, message) -> bool` never raises. `format_kenyan_phone()`
    normalizes to `+254...` (the SDK rejects anything else), `_masked`/`_safe_recipient` keep phone
    numbers safe in logs. **`AT_SMS_BASE_URL` is GONE** — the SDK hardcodes its base URL and
    auto-routes to the sandbox when the username is exactly `"sandbox"`. If `AT_USERNAME` or
    `AT_API_KEY` is unset (dev default) it logs a **WARNING** and skips sending (a "stub" no-op, like
    the KVB stub) — a missing SMS config can never break the flow.
  - New `POST /api/v1/notify` (public, no admin token — decision logged; now **async**, farmer +
    board texts send **in parallel** via threadpool): body `{"event": "match"|"verify", "phone",
    "context"}`. `match` → SMS the **farmer** the clinic name, distance and unique code they just
    saw. `verify` → SMS the **farmer** the verification result AND SMS **the board**
    (`BOARD_NOTIFICATION_PHONE`) a lookup summary (license number, timestamp, caller phone) — a
    **documented stopgap** for the not-yet-built board/reporting layer (architecture §3.8), not the
    real thing.
  - **KYC SMS (2026-08-18):** `submit_document` stores optional `contact_phone` (migration 003) and
    SMSs the farmer a receipt + the board a notification with the **clinic name only** (never the
    farmer's phone); admin approve/reject SMSs the decision + unique code to the latest document's
    `contact_phone` + the board. `GET /verify-license` SMSs the board on each lookup (`notify_board`
    param, default true). All fire-and-forget — an SMS failure never breaks the flow.
  - Thin-adapter discipline intact: the USSD adapter only calls `POST /api/v1/notify` over HTTP
    (`api_client.notify()`), fire-and-forget; it never touches SMS/Africa's Talking directly.
  - **Env vars for real SMS:** `AT_USERNAME`, `AT_API_KEY` (+ optional `AT_SENDER_ID` shortcode),
    `BOARD_NOTIFICATION_PHONE`. All present in `apps/api/.env.example` and docker-compose (`api`
    service). Until then every `send_sms` is a logged WARNING no-op.
- **Tests (2026-08-18):** `apps/api` 114 + `apps/ussd` 73, all green via a local Python 3.14 venv
  (Docker unavailable this session — see §5/STATUS for the pinned-container run to re-verify). New
  coverage: home-vs-end "00" semantics (incl. mid-flow reset keeping language), county 1-letter
  search + page-2 selection by continuous number, service continuous numbering via "98" + custom-
  service flag, optional sub-location skip, EN/SW flows, SDK-backed SMS client (fake SDK), notify
  dispatch, KYC SMS wiring, verify-license board SMS.

### 2.14 Public web dashboard — `apps/web` (2026-08-20)
- **What it is:** a read-only page listing **verified** VetLink254 clinics (name + county + services),
  built in **plain HTML/CSS/JS — no framework, no build step, no Node** (deliberate choice for a
  zero-dependency static site). `app.js` fetches `GET /api/v1/clinics/` from `window.VETLINK_API_BASE`
  (default `http://localhost:8000`, set in `index.html`) and renders only clinics with
  `verification_status === "verified"` (escaping all text — no injection).
- **How it's served locally:** a `web` service in docker-compose (port **8002**) runs
  `python -m http.server` from a 4-line Dockerfile. On Render it deploys as a `static_site` (the
  `render.yaml` blueprint) — you just change `window.VETLINK_API_BASE` to the deployed api URL.
- **CORS:** apps/api now sends `Access-Control-Allow-Origin` (from `CORS_ORIGINS`, dev default `"*"`,
  methods GET/POST/PATCH) so the separate-origin dashboard can read public data. **The `*` default is a
  dev/demo setting — restrict to an explicit origin allow-list before production** (§5.3).
- **Verify (live-tested 2026-08-20):** `curl http://localhost:8002/` + `style.css` + `app.js` all 200;
  `curl -H "Origin: http://localhost:8002" http://localhost:8000/api/v1/clinics/` returns
  `Access-Control-Allow-Origin: *`.

### 2.15 Render blueprint + CI (2026-08-20) — config ready, **NOT yet deployed**
- **`render.yaml`** (root) declares the whole deployment: an **api web service** (docker image,
  `startCommand` = uvicorn, `releaseCommand` = `alembic upgrade head && python -m scripts.create_admin`,
  `healthCheckPath` = `/health`), a **ussd web service** (gunicorn, `API_BASE_URL` wired to the api
  service URL), a **static_site** web, and managed **Postgres + Redis**. All secrets
  (`AT_*`, `ADMIN_*`, `R2_*`, `SECRET_KEY`, `BOARD_NOTIFICATION_PHONE`) are `sync:false` — pasted by
  the user, never committed. **This is deployment configuration, not a deployment** — no Render
  account was connected this session, so nothing is live (see §5.9).
- **`.github/workflows/ci.yml`**: on every push to `main` and every PR, runs `./run_tests.sh` (both
  suites in the pinned 3.11 containers) and `docker build`s the api/ussd/web images. Final
  green-on-GitHub confirmation is pending the first real push.

---

## 3. What's Stubbed or Partially Built

| Item | State |
|---|---|
| **`apps/web`** | **Built 2026-08-20** — plain HTML/CSS/JS verified-clinics dashboard, served on :8002 locally and as a Render static_site. It is read-only (public clinic listing only) — no login, no clinic dashboard, no farmer booking UI, no admin console. |
| **`apps/api` bookings** | Bare CRUD only (GET list / POST create). No booking workflow, no status transitions, no scheduling logic, no booking reference flow from USSD. |
| **`apps/api` users** | Bare CRUD only. No authentication, no OTP, no password, no email-attach flow, no `ussd_only_flag`→verified-account transition logic. |
| **Matching Engine** | Basic Haversine matching works. Missing radius-tier fallback (5km→20km→50km→nearest), wallet-balance/lead-fee filter, geocoding for clinics without coordinates, PostGIS. |
| **Registration / KYC** | Workflow works end-to-end (2026-08-20): **multipart file upload** with MIME allowlist (PNG/JPEG/WebP/PDF) + 10MB cap, stored to **local disk** (`LOCAL_UPLOAD_DIR`, served at `/uploads`) with a **code-complete Cloudflare R2 path** (boto3) that activates once the four `R2_*` env vars are set — **R2 not yet live** (no credentials). Unique-code generator is COUNT-based (not concurrency-safe). |
| **Auth** | **Minimal single-admin JWT auth** (2026-08-20): bcrypt + PyJWT HS256, one admin seeded from env, login endpoint, JWT required on verify + PATCH. Deliberate MVP — no roles, no refresh tokens, no OTP, no login UI, no rate limiting. |
| **USSD** | Two flows: "find a vet" (language → animal → catalogue w/ continuous numbering "98"=next page → 47-county type-to-search w/ shared pagination → optional sub-location (9 to skip) → results → details) and "verify a vet" (license number → live KVB status, stub). Bilingual EN/SW. Find-a-vet ends at a **read-only** clinic-details screen — booking creation, wallet top-up, clinic registration and check-status flows from the original prototype were **deliberately not ported**. 5 animals, ~24 services (3 pages, continuous numbers + free-text custom service), 47 counties via type-to-search with **approximate centroid coords** (no geocoding). "0"/"00" nav: context-dependent home-vs-end (see §2). |
| **SMS notifications** | **STUB/no-op** until Africa's Talking creds set (`AT_USERNAME`/`AT_API_KEY`; username `"sandbox"` routes to the AT sandbox). Official **africastalking SDK** (pinned 2.0.3), `SMSClient` + `POST /api/v1/notify` wired: farmer SMS on match + verify; board stopgap SMS on verify; KYC submit/approve/reject SMSs; `verify-license` board SMS per lookup. Nothing is actually sent until creds exist. The board SMS is a **stopgap**, not the real reporting layer. |
| **KVB license verification** | **STUB ONLY** — works end-to-end via a temporary stub (`KVBVerificationClient`, `GET /api/v1/verify-license`, USSD "Verify a vet" branch) that returns canned data for a few fake license numbers and logs a WARNING. Real KVB integration is **externally blocked** (KVB has no public API yet; needs a data-sharing agreement, see §5.12). |
| **Telecom gateway** | No real gateway. `/simulate` + `POST /ussd` stand in for Africa's Talking / an aggregator. |
| **Deployment** | `render.yaml` is written and validated by inspection but **NOT deployed** (no Render account connected). `docker-compose.yml` remains the only way anything actually runs tonight. |

---

## 4. What's Not Built Yet

Everything below is part of the original vision (architecture.md) with **no code at all** (or only a
minimal seed built in the 2026-08-20 pass):

- **Real KVB integration** — the license-verification bridge works against a temporary STUB only;
  calling the real KVB API (and any Pesaflow/eCitizen levy routing, if a levy is ever introduced) is
  blocked on KVB exposing a public API + formal data-sharing/agreement steps (§5.12).
- **Wallet & payments** — wallet tables/ledger, mobile-money push payments, top-up, lead-response
  fee, clinic payout. No payment-gateway decision has been made. (The wallet/M-Pesa notes are the
  FARMER→CLINIC payment path; any KVB-related levy would route via Pesaflow/eCitizen, not a private
  paybill — see §5.12.)
- **Full authentication** — the 2026-08-20 pass added a deliberate single-admin JWT MVP only. Roles
  (farmer / vet / clinic / admin), phone OTP, refresh tokens, a login UI and rate limiting per
  architecture §3.5 / §6 are still to build.
- **Telecom gateway integration** — an actual aggregator (e.g. Africa's Talking), a short code,
  a public HTTPS webhook endpoint, webhook auth/HMAC. (`/simulate` + `POST /ussd` sandbox only today.)
- **Booking creation from USSD** — the USSD flow currently ends at read-only clinic details.
- **The full website (`apps/web`)** — only the public verified-clinics listing exists (plain
  HTML/CSS/JS, 2026-08-20). Farmer / clinic / admin / public-facing site with auth (Next.js + Tailwind
  per architecture §8) is still not built.
- **Notifications (full)** — an SMS stub exists (Africa's Talking via `POST /api/v1/notify`, no-op
  until `AT_USERNAME`/`AT_API_KEY` are set); email + push, booking-confirmed/failed triggers,
  vaccination-due reminders, and the board/reporting layer are still not built.
- **Board / national reporting layer** — de-identified analytics rollups for the veterinary board
  (disease clustering, vaccination coverage, clinic density).
- **Geocoding** — clinics without lat/lng are silently excluded from matching today.
- **Background jobs / workers** — reminders, report rollups, payouts (Celery/RQ).
- **Live deployment** — `render.yaml` exists (config only) and CI exists, but nothing is deployed;
  the docker-compose stack is the only thing that runs.
- **`packages/` (shared UI), `infra/` (k8s/terraform/nginx), `apps/mobile`** — not created.

---

## 5. Known Limitations & Honest Gaps

This section is deliberately unsoftened — it exists so someone making a real deployment decision can
judge readiness. **This is NOT production-ready, and it is not close.**

1. **Auth is a single-admin MVP, not full authentication.** The 2026-08-20 pass replaced the shared
   `X-Admin-Token` with one admin user + bcrypt + HS256 JWT on the same two endpoints (verify, PATCH).
   Everything else — creating clinics, submitting documents, matching, all reads, login itself — is
   still open. No roles, no refresh tokens, no phone OTP, no login UI, no rate limiting, no lockout.
   Before any real deployment this must grow into JWT + phone OTP + role-based access control.

2. **No telecom gateway. No short code. No public HTTPS endpoint.** The USSD service is reachable
   only at `localhost:8001`. A real telco integration (Africa's Talking or another East African
   aggregator) requires: an application/provisioning account, a short code (`*XXX#`), a public
   HTTPS URL for the webhook, and lead time for telecom approval that is **out of this project's
   control**. The `/simulate` endpoint is a stand-in only.

3. **CORS is wide open on USSD *and* the API.** `origins: "*"` on `/simulate` and `/ussd` (both
   unauthenticated), and the API's `CORS_ORIGINS` dev default is `"*"` (needed for the separate-origin
   dashboard to read public data). Any website on the internet can call these endpoints from a
   browser. **Must** be restricted to an explicit origin allow-list before any deployment beyond
   localhost (a real telecom gateway never needs CORS at all).

4. **Only test data exists — no real clinic onboarding.** The database contains a handful of test
   clinics (e.g. "PetCare Global Clinic" VL254-KE-00002, "Texas Vet Partners" VL254-US-00002) and
   test documents (now real local files under `LOCAL_UPLOAD_DIR` during the demo, not fake S3 URLs).
   No real clinic has onboarded, no real verification authority has been involved.

5. **No security review.** No threat modelling, no penetration testing, no secret management
   (JWT `SECRET_KEY` + admin creds in dev defaults/plaintext env), no rate limiting, no input
   sanitisation review, no dependency audit.

6. **No load testing.** Nothing has ever been tested under concurrent USSD load or concurrent
   clinic approvals. The unique-code generator is COUNT-based and **not concurrency-safe** (two
   simultaneous approvals can produce the same code); the DB is a single small Postgres container.

7. **No wallet/payment decision made.** The monetisation model (mobile-money push payments,
   lead-response fees, clinic prepaid wallets) is fully specified in architecture.md but has **zero
   code** and **no chosen provider**, so there is no revenue path implemented.

8. **Tests are green but the pinned-container run + CI-green-on-GitHub are pending, and the USSD
   suite is lighter than the API suite.** `apps/api` (138 tests, ~96%) and `apps/ussd` (73 tests) are
   all green and cover the matching engine, registration service, every API endpoint (incl. auth
   login/401/403, multipart upload 415/413, `/notify` + KYC SMS wiring), the storage client (local +
   fake-boto3 R2), the SMS client (SDK-backed: stub + fake-SDK live path), the KVB bridge (stub +
   cache + endpoint + board SMS), and the USSD menu tree / session store / find-a-vet flow /
   verify-a-vet flow / county search / continuous-numbered pagination / optional sub-location /
   home-vs-end "00" nav / bilingual rendering. Still missing: a docker-compose integration test, USSD
   HTTP-layer tests (`/ussd`, `/simulate`, `/health`, CORS), and (this session) a Docker-enabled run
   of `./run_tests.sh` against the pinned deps — the 2026-08-20 run used a Python 3.14 venv with
   unpinned latest deps, and the CI workflow's green run is pending the first push.

9. **Dev conveniences baked in.** `create_all` was REMOVED from startup (2026-08-20; Alembic is now
   the sole schema mechanism, run automatically by the start/release commands), but `SECRET_KEY` and
   the admin credentials still have dev defaults (docker-compose), and the demo runs on SQLite where
   it can. Cloudflare R2 storage is code-complete but NOT live (no credentials) — local disk only.

10. **Scope limits of the USSD flow.** No booking creation, no returning-user last-known-ward, no
    GPS. Location is the USSD-native type-to-search over all 47 counties using **approximate county
    centroids** (sub-locations are free text and not geocoded — matching uses the county centroid
    until real geocoding is built; logged as a known approximation, not a bug). Emergency currently
    matches zero clinics because none in the test data offer it.
11. **SMS is STUB/no-op until `AT_USERNAME` + `AT_API_KEY` are set** (logs a WARNING per skipped
    send). The board SMS (`BOARD_NOTIFICATION_PHONE`) is a **documented stopgap** — a minimal SMS
    stand-in for the board/reporting layer (architecture §3.8), not the real thing.

12. **Real KVB integration is EXTERNALLY BLOCKED — the license bridge runs on a STUB today.**
    VetLink254 is a B2C bridge: it checks a vet's license by calling OUT to KVB's own
    practitioner-management system (MMS, `mms.kenyavetboard.or.ke`) — it is NOT the authority on who
    is licensed. KVB does not yet expose a public API, so `GET /api/v1/verify-license` returns canned
    stub data (with a WARNING logged per call) until: (a) KVB exposes a REST API — which requires
    their IT department and a formal data-sharing agreement under the Data Protection Act 2019 — and,
    if a payment levy is ever introduced, (b) a **Pesaflow / eCitizen** integration agreement (KVB has
    moved off private paybills onto the government gateway + unified `*222#` USSD). **This is not a
    coding gap — it is a partnership/government-process dependency outside this project's control.**
    The wallet/M-Pesa notes in this doc are the separate FARMER→CLINIC payment path, not the KVB
    relationship.

13. **NOTHING IS DEPLOYED.** `render.yaml` is written and validated by inspection, but no Render
    account was connected this session, so the api/ussd/dashboard run only via docker-compose (or the
    local harness used for the 2026-08-20 walkthrough). Everything credential-gated is "code complete,
    not yet live-verified — pending <credential>": Render deploy (account), real SMS (AT creds), USSD
    short code + public webhook (telco provisioning), R2 storage (R2 creds), the dashboard's public
    URL (static_site deploy), and CI-green on GitHub (first push).

---

## 6. How To Run Everything From Scratch (a brand-new developer on a clean machine)

Assumes **nothing** is set up yet. Install the prerequisites first; then clone, run, and verify.

### 6.1 Prerequisites (you must install these yourself)
- **Git** — https://git-scm.com/downloads
- **Docker Desktop** (includes Docker Engine + Docker Compose v2+):
  - Windows / macOS: https://docs.docker.com/get-docker/ (Docker Desktop)
  - Linux: https://docs.docker.com/engine/install/
  - Docker Compose ships with Docker Desktop; standalone install: https://docs.docker.com/compose/install/
- **curl** — https://curl.se/download.html (built into macOS; install via your Linux package manager)
- **Nothing else.** No Python, no Node, no local Postgres — everything runs in containers.

### 6.2 First steps
```bash
# 1. Clone the repository
git clone <your-repo-url> vetlink254
cd vetlink254

# 2. Start the whole stack (api, ussd, web, postgres, redis) — first run builds images, so allow a few minutes
docker compose up --build -d

# 3. Confirm all five containers are up (api also runs alembic upgrade head + admin seed on start)
docker compose ps
#    vetlink_api      Up  0.0.0.0:8000->8000/tcp
#    vetlink_ussd     Up  0.0.0.0:8001->8001/tcp
#    vetlink_web      Up  0.0.0.0:8002->8002/tcp
#    vetlink_postgres Up  0.0.0.0:5432->5432/tcp
#    vetlink_redis    Up  0.0.0.0:6379->6379/tcp

# 4. Sanity-check the APIs
curl -s http://localhost:8000/health        # {"status":"ok"}
curl -s http://localhost:8001/health        # {"redis":"connected","status":"ok"}
curl -s http://localhost:8002/              # dashboard index.html
```

### 6.3 See a full working flow in ~2 minutes
```bash
# 0. Log in as the seeded admin (dev default creds) and capture a JWT
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" \
  -d '{"email":"admin@vetlink254.local","password":"dev-admin-password-change-me"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# A. Create a clinic
curl -s -X POST http://localhost:8000/api/v1/clinics/ -H "Content-Type: application/json" \
  -d '{"name":"My Clinic","county":"Nairobi","verifying_authority":"KVB-KE"}'          # note its id

# B. Submit a KYC document (replace <ID> with the clinic id) — real multipart file upload
curl -s -X POST http://localhost:8000/api/v1/clinics/<ID>/documents \
  -F "file=@/tmp/licence.pdf" -F "doc_type=license" -F "contact_phone=+254712345678"

# C. Approve it (JWT from step 0)
curl -s -X POST http://localhost:8000/api/v1/clinics/<ID>/verify -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"decision":"approved","reviewed_by":"admin@vetlink254","reason":"ok"}'           # -> verified + VL254-KE-xxxxx

# D. Give it a location + services so it can be matched (JWT)
curl -s -X PATCH http://localhost:8000/api/v1/clinics/<ID> -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"lat":-1.2833,"lng":36.8167,"services":["consultation","vaccination"]}'

# E. Match it from a nearby point
curl -s "http://localhost:8000/api/v1/match/?lat=-1.2921&lng=36.8219&service=consultation"

# F. See it on the public dashboard (served by the web service, reads from the api)
curl -s http://localhost:8002/   # open in a browser; app.js fetches /api/v1/clinics/ and lists verified clinics

# G. Walk the USSD "find a vet" flow (English, Consultation from Nairobi)
curl -s "http://localhost:8001/simulate?session_id=new1&text="
curl -s "http://localhost:8001/simulate?session_id=new1&text=1"             # English
curl -s "http://localhost:8001/simulate?session_id=new1&text=1*1"           # Find a vet
curl -s "http://localhost:8001/simulate?session_id=new1&text=1*1*1"         # animal -> service (Page 1/3)
curl -s "http://localhost:8001/simulate?session_id=new1&text=1*1*1*1"       # consultation -> county search
curl -s "http://localhost:8001/simulate?session_id=new1&text=1*1*1*1*nai"   # -> "1. Nairobi"
curl -s "http://localhost:8001/simulate?session_id=new1&text=1*1*1*1*nai*1" # Nairobi -> sub-location prompt
curl -s "http://localhost:8001/simulate?session_id=new1&text=1*1*1*1*nai*1*Kilimani"   # -> results from /api/v1/match
curl -s "http://localhost:8001/simulate?session_id=new1&text=1*1*1*1*nai*1*Kilimani*1" # -> clinic details (END)
```

### 6.4 If the database schema needs rebuilding (fresh clone)
Alembic is the **sole schema mechanism** — the api start command runs `alembic upgrade head` itself
(and seeds the admin), so on docker-compose you normally do nothing. If you want to run it manually:
```bash
# From inside the api container (container already running)
docker exec vetlink_api alembic upgrade head
```
The data persists in the `postgres_data` Docker volume across restarts; to start completely fresh:
```bash
docker compose down -v   # destroys the postgres volume — ALL data is lost
docker compose up --build -d
```

### 6.5 Editing code and seeing it live
Code is volume-mounted (`./apps/api:/app`, `./apps/ussd:/app`), so edits appear in the containers
immediately, but the servers run without `--reload`:
```bash
docker restart vetlink_api    # after editing apps/api
docker restart vetlink_ussd   # after editing apps/ussd
```
Dependency changes (requirements.txt / Dockerfile) require a rebuild instead:
```bash
docker compose up --build -d
```

---

## 7. Next Steps, In Suggested Order

Based on everything built so far and the gaps above — ordered by what unblocks the most value / de-risks fastest:

1. **Deploy to Render.** Everything that can be made live is `render.yaml`-ready but **nothing is
   deployed** (no Render account was connected this session). Create the account, connect the repo,
   paste the `sync:false` secrets (AT_*, ADMIN_*, R2_*, SECRET_KEY, BOARD_NOTIFICATION_PHONE), let it
   provision managed Postgres + Redis, then edit `apps/web/index.html` `window.VETLINK_API_BASE` to
   the deployed api URL. Confirm the api releaseCommand + USSD `API_BASE_URL` render references.
2. **Set the real external credentials to go live, each one independently gated:** Africa's Talking
   (`AT_USERNAME`/`AT_API_KEY`, username `"sandbox"` routes to the sandbox) to turn SMS on; a real
   short code + public HTTPS webhook for the USSD gateway; the four `R2_*` env vars to switch KYC
   storage from local disk to Cloudflare R2. Each is code-complete and needs only the credential + a
   live test.
3. **Full authentication (JWT + phone OTP + roles).** The 2026-08-20 pass delivered a single-admin
   MVP only. The real target: admin/board role for verify, clinic-owner auth for PATCH, a decision on
   farmer USSD identity (phone OTP), refresh tokens, a login UI, rate limiting.
4. **Harden the dev-only surfaces before ANY exposure:** restrict or remove USSD CORS **and** the API
   `CORS_ORIGINS` `"*"` default, lock down `/simulate`, and replace the dev-default `SECRET_KEY` /
   admin credentials with secrets management.
5. **Decide and build the wallet/payments layer** (architecture §3.6 / §6): wallet tables + ledger,
   mobile-money push integration, lead-response fee, clinic payout split. This is the monetisation
   core and everything (matching's wallet-balance filter, USSD top-up flow, the clinic dashboard)
   hangs off it.
6. **Bookings engine** — turn the bare CRUD into the real booking workflow (requested → matched →
   confirmed → completed → cancelled) and wire USSD's results screen to actually create a booking.
7. **Telecom gateway integration** — start the provisioning conversation with an aggregator early
   (lead time is external), then implement the webhook endpoint with auth/HMAC + a public HTTPS URL.
8. **Expand USSD data further** — real ward-level location list (beyond county-centroid search), returning-user last-known-ward, emergency routing. County search now covers all 47 counties (approximate centroids) and the service catalogue is ~24 items with pagination; add geocoding so clinics without coordinates can be matched and sub-locations resolve precisely.
9. **Extend `apps/web`** — a read-only verified-clinics listing exists (2026-08-20, plain
   HTML/CSS/JS). The full site (clinic dashboard with leads inbox + wallet, farmer booking UI, admin
   console, auth) is what makes the platform legible to real users.
10. **PostGIS migration + radius-tier fallback** for the matching engine once clinic volume grows.
11. **Notifications + board reporting layer** last — they need real usage data to be meaningful.
12. **Swap the KVB stub for the real KVB endpoint (drop-in).** Once KVB exposes a public REST API,
    set `KVB_API_BASE_URL` to the real endpoint and supply real `KVB_CLIENT_ID`/`KVB_CLIENT_SECRET`
    (OAuth2 client-credentials) — the stub logs a WARNING and the real client calls `POST /oauth/token`
    then `GET /api/v1/verify/{license_number}`. **No other code changes should be needed** if the
    interface (`verify_license() -> {status, name, license_type}`) is respected; confirm the real
    endpoint shapes against KVB's API docs when they exist. The per-session Redis cache (180s TTL) is
    the only intended network saving and never persists license status to Postgres.

---

*This file is a durable reference. Session-by-session history lives in `docs/progress/LOG.md`;
the living one-glance snapshot lives in `docs/progress/STATUS.md`; the original product vision
lives in `docs/architecture.md`.*
