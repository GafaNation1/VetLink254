# VetLink254 — Current Status Snapshot (living document, updated each session)

## What's built
- **DEMO-READINESS PASS (2026-08-20, PARTS 1–8).** Render blueprint (config only, NOT deployed), minimal JWT auth replacing the shared admin token, R2 KYC storage with a local-disk fallback, a public verified-clinics dashboard, CI, and a clean isolated git history pushed to GitHub (tag `v0.1.0-demo`). Nothing that needs an external credential is claimed live — everything is marked "code complete, not yet live-verified — pending <credential>" (see the full LOG.md entry dated 2026-08-20 for every file/decision/test).
  - **Auth (VERIFIED live):** one admin seeded from `ADMIN_EMAIL`/`ADMIN_PASSWORD` env vars (idempotent, bcrypt into `users.password_hash`, migration `004`); `POST /api/v1/auth/login` → HS256 JWT (PyJWT, SECRET_KEY); `verify` + `PATCH /clinics/{id}` now require `Authorization: Bearer <JWT>` (401 no/bad token, 403 non-admin). DELIBERATE MVP — single admin role, no refresh/OTP/roles/login UI. Replaces the `X-Admin-Token` stopgap.
  - **File storage (local VERIFIED live; R2 code-complete):** `POST /clinics/{id}/documents` is now a MULTIPART file upload (file/doc_type/contact_phone) with a MIME allowlist (PNG/JPEG/WebP/PDF) + 10MB cap (415/413). With R2 env vars set → Cloudflare R2 via pinned boto3; unset → local disk (`LOCAL_UPLOAD_DIR`, served at `/uploads`). R2 verified via a fake boto3 client only — pending real R2 creds.
  - **Public dashboard (VERIFIED live):** `apps/web/` — plain HTML/CSS/JS, no build step, reads `GET /api/v1/clinics/` and shows verified clinics; served on :8002 in docker-compose and as a Render static_site. API CORS added (`CORS_ORIGINS`, dev default `*` — tighten before production).
  - **CI (config ready):** `.github/workflows/ci.yml` runs `./run_tests.sh` + docker builds of api/ussd/web on push/PR. Final green-on-GitHub confirmation is a follow-up after the push.
  - **Render (config ready, NOT deployed):** `render.yaml` blueprint — api web service (releaseCommand `alembic upgrade head && python -m scripts.create_admin`), ussd web service, static_site web, managed Postgres + Redis, secrets `sync:false`.
  - **Migrations now self-serve:** `create_all` removed from app startup; Alembic is the sole schema mechanism, run automatically at container start.
  - Tests: **apps/api 138 passed (~96%), apps/ussd 73 passed** (unpinned venv — pinned 3.11 container run still pending Docker).
- **USSD NAV REWORK + REAL AT SDK SMS + KVB CONTRACT DOC (2026-08-18).**
- **USSD NAV REWORK + REAL AT SDK SMS + KVB CONTRACT DOC (2026-08-18).**
  - **"0"/"00" navigation reworked:** "0" = Back (only shown when a screen has somewhere to go back to); "00"/"000" is now CONTEXT-DEPENDENT — on the **Welcome/Home screen it ENDS the session**, on **any other screen it jumps straight home WITHOUT ending the session**, resetting in-progress selections but keeping the language choice. Footer rule: "00. End" only on Home; "00. Home" everywhere else.
  - **County search unrestricted + shared pagination:** type **1 letter to the full name** (no length limit), zero matches → clear retry; more than 9 matches paginate with the SAME continuous-numbering pattern as services.
  - **~24-service catalogue with CONTINUOUS numbering** across pages (page 1 = 1-9, page 2 = 10-18, page 3 = 19-24 + "25. Type a service not listed" free-text custom entry, flagged `context["custom_service"]=True`). Reserved next-page key **"98"** (design rule: keep totals < 90).
  - **Optional sub-location:** "Type your area, or reply 9 to skip:" — "9" is a real menu option (nothing stored when skipped); matching still uses the county centroid (logged approximation).
  - **SMS switched to the OFFICIAL africastalking SDK (pinned 2.0.3):** `SMSClient` + `format_kenyan_phone`/`_masked`/`_safe_recipient` in `apps/api/app/integrations/sms_client.py`. Sandbox auto-routes when username="sandbox"; **`AT_SMS_BASE_URL` removed** (dead config — SDK hardcodes base URLs). Stub/no-op until `AT_USERNAME`+`AT_API_KEY` set. `/notify` is now async (farmer + board texts send in parallel via threadpool).
  - **SMS wired into KYC:** `submit_document` stores optional `contact_phone` (migration 003) and SMSs the farmer a receipt + the board a notification with the CLINIC NAME only; admin approve/reject SMSs the decision + unique code to the clinic contact + the board; `GET /verify-license` sends a board SMS per lookup (`notify_board` param, default true). All fire-and-forget — SMS failure never breaks a flow.
  - **`docs/KVB_INTEGRATION.md`** — the agreed contract (assumed OAuth2 token endpoint, `GET {base}/api/v1/verify/{license}`, error mapping, per-session cache, stub dataset, config-only go-live checklist).
  - Tests: **apps/api 114 (was 87), apps/ussd 73 (was 57), all green** (see run note below).
- **NATIONAL USSD + BILINGUAL + SMS NOTIFICATIONS (2026-08-16).** The USSD menu is no longer shallow:
  - **Language first:** the very first screen is "Chagua lugha / Choose language — 1. English 2. Kiswahili"; the choice drives every prompt/label for the session (TRANSLATIONS dict in `menu_tree.py`, EN canonical + SW best-effort; technical SW terms flagged `TODO-SW` for native review).
  - **47-county location search (USSD-native type-to-search, NO GPS):** farmer types letters → case-insensitive county-name filter → up to 9 numbered matches (0 matches → clear retry; >9 → first 9 + "type more letters to narrow"). Coordinates are **APPROXIMATE COUNTY CENTROIDS** (documented limitation: no geocoding infra/key). A free-text sub-location ("Kilimani", "Ruiru town") is stored as text, NOT geocoded — matching uses the county centroid until real geocoding is built.
  - **~24-service catalogue, paginated 9/page** ("0. Back", "00. End", new "#. More options"); the last page's "#" opens free-text custom-service entry, stored + flagged `is_custom_service` (uncatalogued, review later). Canonical service values match clinic `services` case-insensitively; Clinic model unchanged.
  - **SMS notifications (Africa's Talking, STUB-safe):** new `POST /api/v1/notify` (public) + `apps/api/app/integrations/sms_client.py`. `SMSClient.send_sms()` runs in **STUB/no-op mode** (logs WARNING, sends nothing) until `AT_USERNAME` + `AT_API_KEY` are set. Farmer SMS on: match result (clinic name/distance/unique code) and verify result (what they saw). **Board SMS (STOPGAP):** `BOARD_NOTIFICATION_PHONE` gets a short lookup summary on every vet-verification lookup (license, timestamp, caller phone) — a minimal SMS stand-in for the not-yet-built board/reporting layer, not the real thing. Thin adapter intact: USSD only POSTs /notify over HTTP, never touches SMS.
  - Tests: **apps/api 87 (was 74), apps/ussd 57 (was 34), all green** (see run note below).
- **KVB VERIFICATION BRIDGE ADDED (2026-08-15) — STUB ONLY.** New `GET /api/v1/verify-license?license_number=` (public, farmer-facing, no admin token) + a new USSD menu branch "2. Verify a vet" (free-text license number → END "Dr. X is a VERIFIED KVB <type>." / "NOT currently verified" / "Service temporarily unavailable"). Built in `apps/api/app/integrations/kvb_client.py` as a **temporary stub** (`KVB_API_BASE_URL` unset or "stub" → canned data for KVB-1001/1002 active, KVB-1003 expired, else not-found; logs a **WARNING on every stub call**). Real mode is OAuth2 client-credentials → `GET {base}/api/v1/verify/{license_number}` (assumed contract). Successful lookups cached in Redis for 180s (matches USSD session TTL), **never persisted to Postgres**. **Real KVB integration is EXTERNALLY BLOCKED** (KVB has no public API yet; needs IT + Data Protection Act 2019 data-sharing agreement; any levy would route via Pesaflow/eCitizen, not a private paybill) — see CURRENT_STATE §5.12. Distinct from internal clinic onboarding (`verifying_authority`/`POST /clinics/{id}/verify`) — the two concepts are never merged. Tests: API now 74 (was 55), USSD now 34 (was 24), all green (see note below on how this was run).
- **AUTOMATED TEST SUITE ADDED (2026-08-14).** pytest suites for `apps/api` and `apps/ussd`, all green. API suite covers the matching engine (haversine + filters/sort/limit), registration service (unique-code format, region derivation, approve/reject), and every HTTP endpoint via FastAPI TestClient (clinics CRUD + admin-token auth, verification/documents, match, users, bookings). USSD suite covers the menu tree, the real RedisSessionStore (via fakeredis), and the full find-a-vet session flow (in-memory store + mocked api_client). **No business logic changed; no bugs found.** Test DB: isolated file-based SQLite (no Postgres needed); USSD tests need no Redis. Run everything: `./run_tests.sh` from the repo root (single command, throwaway `python:3.11-slim` containers, docker-compose NOT required). Exact per-app commands are in each app's README. API coverage ~99% (408 stmts). Details, choices (SQLite vs Postgres, fakeredis), and gaps logged in `docs/progress/LOG.md` and `docs/CURRENT_STATE.md` §2.10.
- **FULL CLEANUP + COMPREHENSIVE DOCUMENTATION PASS COMPLETED (2026-08-14).** See **`docs/CURRENT_STATE.md`** — the new authoritative, up-to-date reference a brand-new agent/developer reads FIRST (real folder tree, exactly what works with exact commands, what's stubbed/not built, run-from-scratch guide, honest known limitations, and next steps in order). `docs/README.md` indexes all docs; `docs/architecture.md` gained a pointer to CURRENT_STATE.md at the top. Cleanup this pass: deleted 10 `__pycache__` dirs / 35 `.pyc` (gitignored, untracked), found zero empty files/dirs, zero dead code, zero misplaced files, added `apps/ussd/.env.example` (+ wired `env_file` into docker-compose ussd service for env-var parity with the api service), removed the obsolete compose `version` key. Everything was live-re-verified against the running stack: all API endpoints (register→verify→match, PATCH, health), the full USSD→api match walkthrough, Redis session lifecycle, imports in both containers, and the env-var matrix (no missing/orphaned vars). Nothing was found broken, so no business-logic changes were needed. NOTE: the project folder is not under version control yet — `git init` + initial commit is a recommended next step.
- Monorepo skeleton: `apps/ussd/` and `apps/web/` exist with placeholder READMEs only.
- `apps/api/` Core API foundation:
  - FastAPI app (`app/main.py`) with `GET /health`.
  - SQLAlchemy engine + session (`app/core/database.py`), `DATABASE_URL` from env (`app/config.py`, `.env.example`).
  - Models: `User`, `Clinic`, `Booking`, `VerificationDocument` (`app/models/`).
  - Pydantic schemas: `app/schemas/` (User, Clinic, Booking, Verification).
  - Routers v1: `GET /api/v1/{users,clinics,bookings}` list, `POST` create, `GET /api/v1/clinics/{id}`, plus verification routes.
  - Alembic configured; migrations `001_initial_migration`, `002_verification_kyc`, and `003_verification_contact_phone` (head).
  - `requirements.txt` pinned; `Dockerfile` defined.
- `docker-compose.yml` at repo root: `api`, `postgres`, `redis`.
- **Registration & Verification (KYC)** — global scope:
  - `verification_documents` table (doc_type generic: license/id/proof_of_premises/indemnity_insurance/...; status pending/approved/rejected; reviewed_by/reviewed_at/uploaded_at).
  - Clinic fields: `verifying_authority` (e.g. "KVB-KE", "AVMA-US" — Kenya is just one example of a verifying authority), `verification_note`.
  - Endpoints: `POST /clinics/{id}/documents`, `GET /clinics/{id}/documents`, `POST /clinics/{id}/verify` (approve/reject).
  - On approval: clinic → `verified`, unique code issued `VL254-<2-letter-region>-<00001+>` (region derived from verifying_authority, e.g. VL254-KE-00001, VL254-US-00002). On rejection: clinic → `rejected`, reason stored in `verification_note`.
  - Business logic in `app/services/registration_service.py`.
- **Cleanup done this session**: full scan found no empty files/dirs; nothing deleted.
- **Matching Engine** — apps/api only:
  - `app/services/matching_engine.py`: `find_nearest_clinics(db, lat, lng, service, limit=3)` — filters `verification_status == "verified"`, requires the service in the clinic's `services` JSON list (case-insensitive; null/empty services excluded), excludes clinics missing lat/lng (logged DEBUG), computes distance with the **Haversine formula in plain Python** (no PostGIS yet — planned optimization once clinic volume is large), returns closest `limit` sorted ascending.
  - `GET /api/v1/match?lat=..&lng=..&service=..&limit=3` returns matches with a computed `distance_km` (3 dp). `MatchResult` schema in `app/schemas/match.py`.
  - `PATCH /api/v1/clinics/{id}` added (lat/lng/services only, all-optional) so test clinics can get real coordinates.
  - Live-verified: clinic 2 "PetCare Global Clinic" set to lat -1.2833/lng 36.8167 (Nairobi); match from lat -1.2921/lng 36.8219 + `service=consultation` returns clinic 2 with `distance_km: 1.137`; `VACCINATION` (case-insensitive) matches; `grooming` returns `[]` (empty, not error).

- **Stopgap admin-token auth** — apps/api only:
  - `app/core/security.py` `require_admin_token` dependency: `X-Admin-Token` header must equal `ADMIN_API_TOKEN` env var (default `dev-admin-token-change-me`, defined in `config.py`, `.env.example`, `docker-compose.yml`); missing or wrong token → 401 with `"Valid X-Admin-Token header required (admin action)"`.
  - Applied to `POST /clinics/{id}/verify` and `PATCH /clinics/{id}` only. All other endpoints (GET list/detail, POST create, document submission, match) stay open by design (public-ish or farmer/clinic-initiated actions).
  - Live-verified: both endpoints 401 without/wrong token, 200 with correct token; open endpoints unaffected.

- **USSD thin adapter** — apps/ussd (Flask), "Find a Vet" flow only:
  - `POST /ussd` webhook (sessionId/phoneNumber/text, `*`-separated, `CON`/`END` bodies) + `/simulate` sandbox (Africa's Talking-style, curl-walkable) + `/health`.
  - Redis-backed session state (key `ussd:session:{id}`, node + collected choices, 180s TTL, deleted on END screens). Redis unreachable => logged as a BLOCKING issue + "END Service temporarily unavailable"; NO in-memory fallback (statelessness).
  - Declarative menu tree: Welcome → Find a vet → animal (Dog/Cat/Cattle/Poultry/Other) → service (Consultation/Vaccination/Emergency) → location (Westlands/Kasarani/Embakasi/Dagoretti, fixed lat/lng since USSD has no GPS) → results (top 3, name + distance) → clinic details (END).
  - Thin adapter: holds NO business logic, NO DB access. Matching delegated to `apps/api` `GET /api/v1/match` via `requests`. Bookings/wallet/payment explicitly NOT built this step.
  - `ussd` service added to docker-compose (port 8001, depends on api+redis). Rebuilt from the user's existing Flask USSD prototype at `Downloads/ussd test/app.py` — its webhook conventions were reused, its embedded business logic was stripped.
  - Live-verified end-to-end: clinic 2 "PetCare Global Clinic" matched from Westlands (2.216 km), Kasarani (10.442 km), Embakasi (11.445 km), Dagoretti (7.926 km); Emergency → clean no-match END; back/00 nav + Redis TTL/deletion verified; POST /ussd gateway format verified.
- **CORS (dev-only) — apps/ussd only** (so a browser page can call `http://localhost:8001` from another origin, for a local phone-simulator UI):
  - `flask-cors==4.0.1` added to `apps/ussd/requirements.txt`; `CORS(app, resources={"/simulate": {"origins": "*"}, "/ussd": {"origins": "*"}})` in `apps/ussd/app/main.py`. Flask-cors reflects any request Origin (allow-all) when one is sent, or emits `*` when absent. `/health` (and any non-listed route) gets NO CORS headers.
  - Verified live: GET /simulate and POST /ussd with an Origin header return `Access-Control-Allow-Origin`; OPTIONS preflight returns 200 with `Access-Control-Allow-Origin` + `Access-Control-Allow-Methods`; `/health` and `/nope` return no CORS headers. **DEV-ONLY: MUST be restricted to an origin allow-list (or removed) before any real deployment** — see What's broken / known gaps.

## What's next
- **Swap the KVB stub for the real KVB endpoint (drop-in)** once KVB exposes a public REST API: set
  `KVB_API_BASE_URL` + real `KVB_CLIENT_ID`/`KVB_CLIENT_SECRET`; no other code changes should be needed
  (interface respected). Externally blocked meanwhile.
- **Set real SMS credentials** (`AT_USERNAME` + `AT_API_KEY`, optional `AT_SENDER_ID`,
  `BOARD_NOTIFICATION_PHONE`; username `"sandbox"` routes to the AT sandbox automatically) — SMS is
  currently in STUB/no-op mode, so nothing is actually sent.
- **Geocoding** so county-centroid approximation + sub-location text become real addresses (and so
  clinics without lat/lng can be matched).
- **Native-speaker review of the Kiswahili strings** (flagged `TODO-SW` inline).
- **Pesaflow / eCitizen integration agreement** — only if a KVB levy is ever introduced (not this
  project's call; requires the government gateway agreement).
- **Deploy to Render** (needs a Render account): paste the `sync:false` secrets (AT_*, ADMIN_*, R2_*, SECRET_KEY, BOARD_NOTIFICATION_PHONE), wire a real Postgres/Redis, then edit `apps/web/index.html` `window.VETLINK_API_BASE` to the deployed api URL. render.yaml is ready but NOT yet deployed.
- **Real SMS + short code** — set `AT_USERNAME`/`AT_API_KEY` (username "sandbox" routes to the sandbox), provision the shared short code, expose the `/ussd` webhook at a public HTTPS URL, lock `/simulate` + CORS down. SMS is still STUB/no-op.
- **Real R2 storage** — set the four `R2_*` env vars to switch from the local-disk fallback (verified live) to real Cloudflare R2 (code-complete, tested against a fake client only).
- **Full production auth (JWT + phone OTP + roles farmer/vet/clinic/admin + login UI + refresh/rate-limiting)** — the 2026-08-20 pass delivered a deliberate single-admin MVP only.
- **Restrict CORS** from the dev `*` default to an explicit origin allow-list before production.
- **Real KVB endpoint (drop-in)** once KVB exposes a public REST API — set `KVB_API_BASE_URL` + `KVB_CLIENT_ID`/`KVB_CLIENT_SECRET`; externally blocked meanwhile.
- Expand the USSD test suite to the Flask HTTP layer (`/ussd`, `/simulate`, `/health`, CORS headers, redis-failure paths).
- Radius-tier fallback (5km→20km→50km→nearest regardless) and wallet-balance/lead-fee filter for matching (architecture Section 3.4).
- PostGIS migration of the distance computation once clinic volume is large.
- Geocoding integration so clinics without lat/lng can be matched.
- Wallet & payment tables/services, lead-response fee.
- Real telecom gateway integration; expand animal/service/location lists and add returning-user last-known-ward.
- Booking creation from USSD (free status-only record), wallet & payment, lead-response fee — all future steps.
- Notifications, board/reporting layer.

## What's broken / known gaps
- **Auth (2026-08-20):** the shared `X-Admin-Token` stopgap is GONE, replaced by a single-admin bcrypt+JWT MVP (email/password login → HS256 Bearer token). It is still NOT full production auth — no roles, no refresh tokens, no OTP, no login UI, no rate limiting. Anyone with the seeded admin credentials can verify clinics and PATCH them; open endpoints (GET/POST clinics, documents upload, match, verify-license) stay unauthenticated by design (verify-license is a deliberate public farmer-facing lookup — decision logged).
- **Render config is NOT yet deployed** (no Render account connected this session) — render.yaml + all docs are marked accordingly.
- **SMS is STUB/no-op until `AT_USERNAME` + `AT_API_KEY` are set** (logs a WARNING, sends nothing).
  `BOARD_NOTIFICATION_PHONE` SMS is a **stopgap** for the board/reporting layer (not yet built).
- **R2 file storage is code-complete but NOT live-verified** (no R2 bucket/creds); the local-disk fallback (`LOCAL_UPLOAD_DIR`/`/uploads`) is what was verified live tonight.
- **How the 2026-08-20 test run was executed:** Docker was NOT available in this WSL distro, so
  `./run_tests.sh` (throwaway python:3.11-slim containers, pinned deps) could NOT be run. Both suites
  ran in a local Python 3.14 venv with **unpinned latest** deps: **API 138 passed (~96%), USSD 73
  passed.** The pinned 3.11-container run (which also exercises the exact requirements.txt pins) must
  be re-verified when Docker is available — the CI workflow will do it on GitHub.
- **Board receives TWO SMS per vet verification** (one from `GET /verify-license` per task 15, one
  from `/notify` "verify" event after the flow completes) — documented redundancy until the real
  reporting layer exists, not a bug.
- **County coords are APPROXIMATE CENTROIDS; sub-locations aren't geocoded** — matching uses the
  county centroid until real geocoding is built (documented limitation, not a bug).
- **Real KVB integration is EXTERNALLY BLOCKED (stub only).** `verify-license` returns canned stub
  data today. Requires KVB exposing a REST API + a formal data-sharing agreement (Data Protection Act
  2019); any levy would need a Pesaflow/eCitizen agreement. Not a coding gap — a partnership/gov
  dependency (§5.12). Every stub call logs a WARNING so it can never be mistaken for real.
- **How the 2026-08-18 test run was executed:** Docker was NOT available in this WSL distro, so
  `./run_tests.sh` (throwaway python:3.11-slim containers, pinned deps) could NOT be run this session.
  Instead both suites were run in a local Python 3.14 venv with **unpinned latest** deps: **API 114
  passed, USSD 73 passed.** The pinned 3.11-container run must be re-verified when Docker is available.
- VERIFIED working end-to-end (Steps 1+2): all 3 containers up; `GET /health` ok; clinic create/list/get works; document submit/list works; approve sets `verification_status=verified` + issues `unique_code`; reject sets `rejected` + stores reason (live-tested with test clinics id 2 "PetCare Global Clinic" VL254-KE-00001 and id 3 "Texas Vet Partners" VL254-US-00002). On 2026-08-20 the same clinic path was re-verified live with JWT auth + multipart upload (see the LOG.md entry).
- Matching uses Haversine in Python (no PostGIS), no radius-tier fallback yet, no geocoding, and no wallet-balance lead-fee filter.
- Tests: **API suite (138) + USSD suite (73) all green** — CI workflow now exists (`.github/workflows/ci.yml`) but its green-on-GitHub run is pending the first push; no docker-compose integration test yet, and the USSD suite does not cover the Flask HTTP layer/CORS/redis-failure routes yet. Test deps are in the runtime requirements.txt (bloat; a requirements-dev.txt split is future cleanup).
- Alembic is now the SOLE schema mechanism (create_all removed from app startup); `alembic upgrade head` runs automatically in the api start/release commands and was verified on a fresh DB through `004_admin_auth`.
- unique_code generator is COUNT-based (not concurrency-safe); needs a sequence table for scale.
- Real file/object storage: local-disk fallback live; Cloudflare R2 code-complete but pending real credentials.
- `apps/ussd` and `apps/web` are both built (thin "Find a Vet" adapter + public verified-clinics dashboard, both live-verified — see What's built).
- USSD `/simulate` dev endpoint is unauthenticated (localhost-only ok; lock down before any external exposure).
- **CORS is allow-all on `/simulate` and `/ussd` (dev-only)** — any origin can call these two currently-unauthenticated endpoints. MUST be restricted to an explicit origin allow-list (or removed, especially from `/ussd` — a real telecom gateway never needs CORS) before any deployment beyond localhost.