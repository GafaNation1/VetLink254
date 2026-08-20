# VetLink254 — National Veterinary-Connect Platform

**Author's note.** I am the engineer who built this system, and this README is
written for an audience that includes Kenyan government reviewers and the Kenya
Veterinary Board's technical team — people who need to know precisely what this
software is, how it works, what has been proven, and what has not. I have not
softened the honest gaps, because a deployment decision based on misleading
documentation is worse than one based on uncomfortable truth. Everything below
is grounded in the actual code in this repository and in `docs/CURRENT_STATE.md`,
which is regenerated against the live filesystem and re-verified against the
running stack on every session.

---

## 1. The problem this system exists to solve

Kenya has a veterinary workforce that is registered and regulated by the
**Kenya Veterinary Board (KVB)**, yet the people who most need veterinary
services — smallholder farmers and pastoralists — face two practical barriers:

1. **Trust / license fraud.** A farmer cannot easily tell whether a person
   offering "vet services" actually holds a valid KVB licence. Anyone can print
   a card. There is no cheap, farmer-accessible way to check a practitioner's
   licence status before handing over money or letting them treat an animal.
2. **Access and reach.** Most rural farmers use **feature phones**, not
   smartphones. Internet-based apps, websites and data-heavy tools are
   effectively closed to them: data is expensive and connectivity is patchy.
   **USSD** (`*XXX#` menus) works on every phone on every network and costs a
   few shillings per session, which is why the short code is the primary
   farmer-facing front door.

VetLink254 is a **national veterinary-connect platform** that addresses both:
it lets a farmer *find* a licensed, verified clinic near them, and it lets a
farmer *verify* a named vet's KVB licence before trusting them. **VetLink254 is
not the authority on who is licensed — KVB is.** VetLink254 is a bridge: it
checks KVB's own records live (once KVB exposes an API) and reports the answer.
That boundary is engineered into the system and documented in
`docs/KVB_INTEGRATION.md`.

---

## 2. Architecture: one Core API, two front doors

```
        ┌──────────────────────────────┐
        │  Telecom USSD gateway        │      (Safaricom/Airtel/Telkom via an
        │  (*XXX# short code)          │       aggregator, e.g. Africa's Talking)
        └──────────────┬───────────────┘
                       │ HTTP webhook per keypress
                       ▼
        ┌──────────────────────────────┐
        │  apps/ussd — thin USSD       │      (Flask — menu tree + Redis session
        │  adapter. NO business logic. │       state ONLY; delegates over HTTP)
        └──────────────┬───────────────┘
                       │ GET /match, GET /verify-license, POST /notify
                       ▼
        ┌──────────────────────────────┐      ┌────────────────────────────┐
        │  apps/api — Core API (FastAPI)│ ───▶ │  PostgreSQL (core data)     │
        │  the single source of truth  │      │  Redis (sessions, KVB cache)│
        └──────────────┬───────────────┘      └────────────────────────────┘
                       │                      Cloudflare R2 / local disk (KYC docs)
                       ▼
        ┌──────────────────────────────┐
        │  apps/web — public dashboard │      (static HTML/CSS/JS — verified clinics)
        └──────────────────────────────┘
```

**The core discipline** (enforced structurally, not just by convention): the
USSD adapter contains **no business logic and no database access**. It walks a
declarative menu tree, stores session state in Redis, and makes HTTP calls to
the Core API. Matching, licensing checks, SMS dispatch and every data rule live
in exactly one place — `apps/api` — so the two front doors (USSD and web) can
never drift apart and duplicate rules. The USSD container has no Postgres driver
installed; it is physically incapable of touching the database.

### 2.1 End-to-end flow — "Find a vet"

1. Farmer dials the USSD short code; the first screen asks for **language**
   (English / Kiswahili).
2. The menu walks: animal type → service (a ~24-item catalogue, paginated) →
   county (**type-to-search over all 47 counties** — USSD has no GPS, so
   location is chosen from a list; each county carries an approximate centroid
   used as the match coordinates) → optional sub-location (or skip).
3. The adapter calls `GET /api/v1/match?lat=..&lng=..&service=..` on the Core
   API. The API filters to **verified** clinics offering that service, computes
   distance with the Haversine formula, and returns the nearest few.
4. The farmer sees name + distance, picks one, and gets a details screen with
   the clinic's unique `VL254-<region>-<seq>` code. An SMS receipt is queued.
5. The session ends; the Redis session is deleted.

### 2.2 End-to-end flow — "Verify a vet"

1. From the USSD welcome screen the farmer chooses "Verify a vet" and types a
   **KVB licence number**.
2. The adapter forwards it to `GET /api/v1/verify-license?license_number=...`
   on the Core API.
3. The Core API calls **out to KVB** (via `apps/api/app/integrations/kvb_client.py`,
   OAuth2 client-credentials) and **never stores the result in Postgres** —
   successful lookups are cached in Redis for 180 seconds only (matching the
   USSD session TTL), so status is always re-checked live per session.
4. The farmer sees VERIFIED / NOT currently verified / service-unavailable; a
   board SMS summary is sent (a documented stopgap until the real reporting
   layer is built).

> **Today this runs against a temporary STUB** (see §4). KVB does not yet
> expose a public API. The stub returns canned data for a few fake licence
> numbers and logs a WARNING on every call so it can never be mistaken for a
> real integration. It is a contract placeholder, not a shortcut.

---

## 3. What is real and working today (verified live)

I re-verified every item below live against the running stack on the dates
recorded in `docs/CURRENT_STATE.md`; the automated test suite re-verifies the
behaviour on every run. Concretely working today:

- **Core API** (`apps/api`, FastAPI): users / clinics / bookings CRUD; nearest-
  verified-clinic matching (Haversine); KYC document upload (multipart, MIME
  allowlist PNG/JPEG/WebP/PDF, 10 MB cap); admin approve/reject with unique
  `VL254-<region>-<seq>` code issuance; minimal single-admin JWT authentication;
  SMS dispatch endpoint; `/health`; auto-generated API docs at `/docs`.
- **USSD adapter** (`apps/ussd`, Flask): the full "find a vet" flow and "verify
  a vet" flow, English + Kiswahili, 47-county type-to-search, paginated service
  catalogue, "0"/"00" navigation, Redis-backed sessions (180s TTL). Served
  locally on port 8001; a `/simulate` sandbox and a real gateway-format
  `POST /ussd` webhook are both exercised.
- **Public dashboard** (`apps/web`): a plain-HTML page listing verified clinics,
  served on port 8002, reading public data from the Core API.
- **Local deployment**: `docker compose up --build -d` brings up api (8000),
  ussd (8001), web (8002), Postgres and Redis. On first boot the API runs
  Alembic migrations and seeds the admin account automatically.
- **Test suite + CI**: `./run_tests.sh` runs the full pytest suite in throwaway
  `python:3.11-slim` containers. **211 tests pass** — `apps/api`: **138 tests,
  ~96% coverage of `app/`**; `apps/ussd`: **73 tests**. CI (`.github/workflows/ci.yml`)
  runs the same suite plus Docker builds of all three images on every push/PR.

## 4. What is built but pending a real credential (honest list)

These are **code-complete, not live**. Each is gated on an external credential,
none of which I had when building. Each is independently switchable by setting
environment variables — no code changes required:

| Piece | What is pending | Env vars |
|---|---|---|
| **Deployment to Render** | A Render account + repo connection | — (secrets pasted in the Render dashboard) |
| **Real SMS** | Africa's Talking credentials | `AT_USERNAME`, `AT_API_KEY`, optional `AT_SENDER_ID` |
| **USSD short code + public webhook** | Telecom/aggregator provisioning, a public HTTPS URL | — (external process) |
| **KYC file storage on Cloudflare R2** | R2 bucket + API token | `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` |
| **Dashboard's public URL** | The Render static-site deploy | — |

Until `AT_*` are set, SMS is a logged no-op (never breaks a flow). Until `R2_*`
are set, KYC documents are stored on local disk and served back at `/uploads`.
Both paths are covered by tests.

## 5. What is intentionally still a stub: the KVB integration

**VetLink254 needs three things from KVB, and nothing more.** These are the
subject of a formal data-sharing agreement under the **Data Protection Act,
2019**, and are fully specified in **`docs/KVB_INTEGRATION.md`** — the technical
contract I prepared for KVB's IT team:

1. **A public REST endpoint** to look up a licence by number —
   `GET {base}/api/v1/verify/{license_number}`, returning
   `{status, name, license_type}`.
2. **OAuth2 client-credentials** for VetLink254 to authenticate to that
   endpoint (`KVB_CLIENT_ID`, `KVB_CLIENT_SECRET`).
3. A base URL to point at (`KVB_API_BASE_URL`).

**What VetLink254 explicitly does NOT ask for:**

- **No bulk data export.** VetLink254 queries one licence number at a time, live,
  when a farmer asks. It does not request a dump of KVB's register.
- **No database access.** VetLink254 never touches KVB's systems beyond the
  public API call, and it never persists licence status in its own database.
- **No role in licensing decisions.** KVB approves and revokes licences;
  VetLink254 only reports the current status back to a farmer.

When KVB exposes the endpoint and supplies credentials, going live is a
**config-only change** (set three environment variables). The contract, assumed
endpoint shapes, error mapping and the config-only go-live checklist are all in
`docs/KVB_INTEGRATION.md`.

## 6. Test coverage, CI, and running everything from scratch

**Prerequisites:** Git and Docker Desktop (includes Compose v2+). Nothing else —
no local Python, Node or Postgres is required.

```bash
# 1. Clone and start the whole stack (builds images on first run)
git clone <repo-url> vetlink254 && cd vetlink254
docker compose up --build -d

# 2. Confirm all five containers are up
docker compose ps

# 3. Sanity checks
curl -s http://localhost:8000/health        # {"status":"ok"}
curl -s http://localhost:8001/health        # {"redis":"connected","status":"ok"}
curl -s http://localhost:8002/              # dashboard

# 4. Run the full test suite (both apps, pinned python:3.11-slim containers)
./run_tests.sh
```

The test suite needs no Postgres and no Redis — the API suite runs against an
isolated SQLite fixture and the USSD suite uses an in-memory/fakeredis session
store. It covers the matching engine, the registration/KYC logic, every HTTP
endpoint (including the JWT 401/403 matrix, multipart upload 415/413 paths, and
the R2-via-fake-boto3 path), the SMS client, the KVB bridge (stub + cache +
real-mode HTTP path), the USSD menu tree, session store, and both full flows.
Honest coverage gaps are listed in `docs/CURRENT_STATE.md` §5.

A full ~2-minute walkthrough (create clinic → upload KYC → admin approve →
match → walk the USSD flow) with exact curl commands is in
`docs/CURRENT_STATE.md` §6.

## 7. What happens when the real credentials arrive

Everything is prepared so that supplying credentials is the only remaining step.
The single exhaustive reference for **every** credential, account, key and
login this project needs — where each one comes from, the exact environment
variable name, the exact file/section that reads it, whether it is required for
a minimal deployment or optional, and the order in which a non-engineer should
go through them — is **`docs/DEPLOYMENT_CREDENTIALS.md`** (new in this session).
Follow that checklist top to bottom; each item is independently gated, so you
can go live with SMS before R2, or vice-versa.

## 8. Documentation map

- `docs/DEPLOYMENT_CREDENTIALS.md` — **the credentials checklist for real deployment (read this next)**
- `docs/CURRENT_STATE.md` — **read this first**: exact folder tree, what works, what's stubbed, how to run everything
- `docs/KVB_INTEGRATION.md` — the KVB technical contract (what VetLink254 needs and doesn't need from KVB)
- `docs/architecture.md` — the original product vision / engineering blueprint
- `docs/README.md` — index of how the docs fit together
- `docs/progress/LOG.md` — session-by-session build history
- `docs/progress/STATUS.md` — living one-glance snapshot