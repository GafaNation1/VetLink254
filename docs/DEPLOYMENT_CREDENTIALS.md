# VetLink254 — Deployment Credentials Checklist

**Purpose.** This is the single exhaustive reference for every real-world
credential, account, API key, token and login this project needs before it can
run for real. Nothing here is assumed and nothing is left implicit. It is
ordered as a checklist you can follow top to bottom even if you are not an
engineer, but it keeps the exact technical precision (variable names, exact
file paths and line locations) a developer needs to plug the values in.

> **Status of this document:** written for the session that makes VetLink254
> "ready for real deployment" — every item below is **code-complete and waiting
> for a real value**. **None of the real credentials have been supplied yet**;
> nothing in this document has been filled in with live values. When each
> credential arrives, use this checklist and `docs/KVB_INTEGRATION.md` (for the
> KVB-specific contract).

---

## 0. What you are about to do (one paragraph)

You will (a) create/locate one account per external service, (b) copy the value
it gives you into the correct environment-variable slot of the Render service
(or the local `docker-compose.yml` if you are testing locally), and (c) confirm
the corresponding feature switches from "stub / code-complete" to "live" by
looking at `docs/CURRENT_STATE.md` §4. The whole point of this repository is
that **setting these values is the only remaining step** — no code changes are
needed to go live (the one documented exception is flagged in §11.4).

**Never commit these values.** The repo's `.gitignore` blocks `.env` files, and
the Render secrets are configured with `sync: false` so they are never written
back into `render.yaml` and never committed. If you ever find a real secret in a
committed file, treat it as compromised and rotate it.

---

## 1. Render account + repo connection (REQUIRED — start here)

| Field | Value |
|---|---|
| **What it is** | The hosting account that runs the API, USSD adapter, dashboard, Postgres and Redis |
| **Where to obtain it** | https://render.com — create a free/paid account, then connect your GitHub account |
| **Which repo** | `https://github.com/GafaNation1/VetLink254` (the `main` branch) |
| **How to connect** | Render → New → Blueprint → pick the repo. Render reads `render.yaml` from the repo root and provisions everything it declares (api, ussd, dashboard, Postgres, Redis) |
| **Required for minimal deployment** | ✅ Required |

**Steps:**
1. Create the account at https://render.com and verify your email.
2. In Render → Account → Connections, connect GitHub and authorise access to
   the `GafaNation1/VetLink254` repository.
3. Render → **New → Blueprint** → select the repo → Render proposes the services
   declared in `render.yaml`. Deploy once **with no secrets set** to see the
   infra come up; the services will boot but credential-gated features will run
   in their stub/safe modes (that is the design — a missing credential never
   crashes the flow).
4. Then paste the secrets one by one using §2–§10 below (each is a Render
   "secret" environment variable on the relevant service).

> **On `sync: false`.** Every secret below is declared in `render.yaml` as
> `sync: false`. That means Render **does not** try to read a value from the
> YAML file — it leaves the value for you to type into the Render dashboard for
> that service. Do not put real values in `render.yaml`; put them in the Render
> dashboard's *Environment* tab for each service.

### 1.1 The three Render services you will paste secrets into

| Service (name in render.yaml) | Runs | Where its env vars live in Render |
|---|---|---|
| `vetlink-api` | Core API (FastAPI, port 8000) | Render dashboard → this web service → **Environment** tab |
| `vetlink-ussd` | USSD thin adapter (Flask, port 8001) | same — Environment tab of the ussd service |
| `vetlink-web` | Static dashboard (port 8002) | no env vars needed (reads the API URL from `apps/web/index.html`, see §11.2) |

---

## 2. `SECRET_KEY` (REQUIRED) — JWT signing secret

| Field | Value |
|---|---|
| **Env var name** | `SECRET_KEY` |
| **Where it is read** | `apps/api/app/config.py`, the `SECRET_KEY` setting (line 13) — used to sign/verify JWT admin tokens in `apps/api/app/core/security.py` (lines 52, 57) |
| **Also in** | `apps/api/.env.example` line 9; `docker-compose.yml` `api.environment` block line 13 |
| **Where it comes from** | You generate it (see below) — this is **not** provided by any external service |
| **Required for minimal deployment** | ✅ Required (auth will not work without it) |

**How to generate it** (run once, anywhere Python/bash is available):
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```
Paste the output as the Render `vetlink-api` secret `SECRET_KEY`.

**Rules:**
- Must be **at least 32 bytes / 32 characters** (HS256 requirement). The
  `token_urlsafe(64)` output above is ~86 characters — comfortably over.
- Use a **different random value for production** than the dev default
  (`dev-secret-key-change-in-prod-0123456789abcdef`). Never reuse it.
- If you rotate it, all outstanding JWTs stop validating — that is expected
  (they are short-lived, 24h by default via `ACCESS_TOKEN_EXPIRE_MINUTES`).

---

## 3. `ADMIN_EMAIL` + `ADMIN_PASSWORD` (REQUIRED) — the single admin account

| Field | Value |
|---|---|
| **Env var names** | `ADMIN_EMAIL`, `ADMIN_PASSWORD` |
| **Where they are read** | `apps/api/app/core/security.py` `ensure_admin_user()` (reads `settings.ADMIN_EMAIL` / `settings.ADMIN_PASSWORD`, lines 103–117); seeded by `apps/api/scripts/create_admin.py`; configured in `apps/api/app/config.py` lines 21–22 |
| **Also in** | `apps/api/.env.example` lines 14–15; `docker-compose.yml` `api.environment` block lines 15–16 |
| **Where they come from** | You choose them — these are your own credentials |
| **Required for minimal deployment** | ✅ Required (without them **no admin is seeded** and `POST /api/v1/auth/login` has no user to succeed for; the admin verify/PATCH endpoints become unusable) |

**Steps:**
1. Pick a real inbox you control, e.g. `ops@yourdomain.go.ke` or
   `board-liaison@yourclinic.example`.
2. Set `ADMIN_EMAIL` to it and `ADMIN_PASSWORD` to a **long, random, unique**
   password (generate one the same way as `SECRET_KEY` if you like:
   `python3 -c "import secrets; print(secrets.token_urlsafe(24))"`).
3. Paste both as Render `vetlink-api` secrets.
4. On deploy, `create_admin` seeds/refreshes the admin idempotently. Login:
   `POST /api/v1/auth/login` with `{"email": <ADMIN_EMAIL>, "password": <ADMIN_PASSWORD>}`
   → returns a JWT.

**Rules:**
- Changing `ADMIN_PASSWORD` on redeploy **updates the hash** (the seed script is
  idempotent and refreshes the password every run) — so rotating is trivial.
- This is a **single-admin MVP**, deliberately. Full role-based auth is a
  documented future step (`docs/CURRENT_STATE.md` §5.1) — do not mistake this
  for a multi-user system.

---

## 4. `DATABASE_URL` + `REDIS_URL` — **AUTO-PROVIDED BY RENDER, do NOT hunt for these**

These two are generated by Render from the managed services in `render.yaml`
and wired automatically. **You do not need to obtain them from anywhere.**

| Field | Value |
|---|---|
| **Env var names** | `DATABASE_URL`, `REDIS_URL` |
| **Where they are read** | `DATABASE_URL` → `apps/api/app/config.py` line 10 + `apps/api/app/core/database.py` + `apps/api/alembic/env.py` line 11; `REDIS_URL` → `apps/api/app/config.py` line 11 (KVB cache) and `apps/ussd/app/session_store.py` line 25 |
| **How Render provides them** | `render.yaml` `vetlink-api` env block: `DATABASE_URL` comes from `fromDatabase: vetlink-postgres` (property `connectionString`); `REDIS_URL` comes from `fromService: vetlink-redis` (property `connectionString`). The ussd service's `REDIS_URL` is wired the same way |
| **Where to find them if you ever need the raw string** | Render dashboard → **Postgres** service → *Connections* → *Internal Database URL*; **Redis** service → *Connections*. **You normally never need to** — the blueprint wires them |
| **Required for minimal deployment** | ✅ Required, but **auto-supplied** |

> **Explicitly: do not spend time looking for these.** They are not something
> you create; they are something Render already created and injected. If a
> service boots and cannot reach its DB/Redis, the problem is almost never a
> missing URL — it is that the Postgres/Redis services were not provisioned yet
> (give the blueprint a few minutes on first deploy).

---

## 5. Africa's Talking — USSD short code + SMS (`AT_USERNAME`, `AT_API_KEY`, `AT_SENDER_ID`)

| Field | Value |
|---|---|
| **Env var names** | `AT_USERNAME`, `AT_API_KEY`, optional `AT_SENDER_ID` |
| **Where they are read** | `apps/api/app/config.py` lines 51–53; consumed by `apps/api/app/integrations/sms_client.py` (via the official `africastalking` SDK, pinned 2.0.3) |
| **Also in** | `apps/api/.env.example` lines 41–43; `docker-compose.yml` `api.environment` block lines 22–24; `render.yaml` `vetlink-api` secrets (sync:false) |
| **Where they come from** | **Africa's Talking developer portal** → https://africastalking.com (sign up), then https://build.at-labs.io or the dashboard → **SMS → Sandbox** (test) or **Go Live** (production) |
| **Required for minimal deployment** | ⚠️ **Optional.** Without them, SMS is a logged no-op ("stub") — nothing is sent, and **nothing breaks**. SMS is what turns on the farmer-receipt / board-notification messages. |

**Steps (recommended order):**
1. Create an Africa's Talking account at https://africastalking.com.
2. Go to **Settings → API Key** to generate your **live** API key (or use the
   sandbox key while testing).
3. **Sandbox vs live** — a critical distinction, and the SDK handles it
   automatically:
   - **Sandbox (testing):** set `AT_USERNAME` to exactly `"sandbox"`. The SDK
     auto-routes to `https://api.sandbox.africastalking.com` and you use the
     sandbox API key. SMS is *simulated* — nothing real is delivered.
   - **Live (production):** set `AT_USERNAME` to your **Africa's Talking
     username** (the account name, not an email) and `AT_API_KEY` to the live
     API key. SMS is delivered for real and costs airtime/credits.
4. `AT_SENDER_ID` (optional): your approved **alphanumeric sender ID** (e.g.
   `VETLNK`) or numeric shortcode for SMS. If you leave it empty the SDK uses
   the default. **Note:** for the **USSD** service the short code is a separate
   item — see §5.1.
5. Paste `AT_USERNAME`, `AT_API_KEY`, `AT_SENDER_ID` as Render `vetlink-api`
   secrets.

### 5.1 The shared USSD short code (separate from SMS)

| Field | Value |
|---|---|
| **What it is** | The `*XXX#` number farmers dial. This is a **telco short code** (Safaricom/Airtel/Telkom), not an API key |
| **Where it comes from** | Via Africa's Talking (they resell short codes in Kenya) — https://africastalking.com → **USSD**. You purchase/lease a short code and Africa's Talking assigns it; approval is done by the telcos and **takes lead time (weeks), entirely outside this project's control** |
| **Where it is configured** | In the **Africa's Talking dashboard** when you set up the USSD product — you point the short code's callback to your public HTTPS `POST /ussd` endpoint (see §11.1) |
| **Required for minimal deployment** | ⚠️ **Optional.** Without it, USSD is reachable only via the `/simulate` sandbox and a direct `POST /ussd` — no farmer can dial in |
| **Notes** | The code itself does **not** live in this repository (it is a telco provision). The webhook it triggers is `apps/ussd/app/main.py` → `POST /ussd`. You must also configure `API_BASE_URL` on the ussd service (§11.1) so the webhook knows the API address |

---

## 6. Cloudflare R2 — KYC document storage (`R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_BASE_URL`)

| Field | Value |
|---|---|
| **Env var names** | `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, optional `R2_PUBLIC_BASE_URL` |
| **Where they are read** | `apps/api/app/config.py` lines 61–67; consumed by `apps/api/app/integrations/storage_client.py` (`r2_configured()` line 109 checks ALL four of the first four are set; `R2StorageClient` uses them in `__init__` lines 79–88) |
| **Also in** | `apps/api/.env.example` lines 50–56; `docker-compose.yml` `api.environment` block lines 27–31; `render.yaml` `vetlink-api` secrets (sync:false) |
| **Where they come from** | **Cloudflare dashboard** → R2 (https://dash.cloudflare.com → R2) |
| **Required for minimal deployment** | ⚠️ **Optional.** Without them, KYC documents are stored on **local disk** (`LOCAL_UPLOAD_DIR`, served at `/uploads`) — works, but not durable/global. R2 is what makes file storage production-grade |

**Steps:**
1. Create a Cloudflare account, then enable **R2** in the dashboard.
2. **Create a bucket** — its name is `R2_BUCKET_NAME` (e.g. `vetlink254-kyc`).
   Set the location to your nearest region (`auto` is the recommended setting —
   the code passes `region_name="auto"`).
3. **Create an API token**: R2 → *Manage R2 API Tokens* → Create token with
   **Object Read & Write** permission scoped to that bucket. Cloudflare returns:
   - **Access Key ID** → `R2_ACCESS_KEY_ID`
   - **Secret Access Key** → `R2_SECRET_ACCESS_KEY` (shown once — copy it now)
4. **Endpoint URL**: in the R2 bucket → *Settings* → copy the **S3 API** URL
   (e.g. `https://<accountid>.r2.cloudflarestorage.com`) → `R2_ENDPOINT_URL`.
5. **Public URL (optional)**: if you want public links to KYC files, enable the
   bucket's *Public access* and use the `pub-<hash>.r2.dev` URL →
   `R2_PUBLIC_BASE_URL`. If left unset, the code builds a private S3-style URL
   instead (fine if files are only ever retrieved internally).
6. Paste all four (five) as Render `vetlink-api` secrets.

> **How the switch works:** the storage client uses R2 **only when all four of
> `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`
> are non-empty**. If any one is empty it falls back to local disk. So a partial
> R2 config silently stays on local disk — set all four together.

---

## 7. `BOARD_NOTIFICATION_PHONE` — board SMS stopgap

| Field | Value |
|---|---|
| **Env var name** | `BOARD_NOTIFICATION_PHONE` |
| **Where it is read** | `apps/api/app/config.py` line 54; used by the SMS dispatch paths in `apps/api/app/api/v1/notify.py`, `apps/api/app/api/v1/verification.py` (KYC submit/approve/reject) and `apps/api/app/api/v1/kvb.py` (per-lookup board summary) |
| **Also in** | `apps/api/.env.example` line 44; `docker-compose.yml` `api.environment` block line 25; `render.yaml` `vetlink-api` secret (sync:false) |
| **Where it comes from** | You choose it — a **Kenyan mobile number in `+2547...` format** that receives the board's SMS summaries (format is enforced by `format_kenyan_phone()` in `sms_client.py`) |
| **Required for minimal deployment** | ⚠️ **Optional.** Without it (or without `AT_*`), the board SMS is simply not sent |

**What it does:** every vet-verification lookup and every clinic KYC
submit/approve/reject sends a short SMS summary to this number — a documented
**stopgap** standing in for the board/reporting layer that is not built yet
(`docs/CURRENT_STATE.md` §4). Format must be `+2547XXXXXXXX` (a real Kenyan
mobile line you control).

---

## 8. KVB — externally blocked, **do not try to obtain yet** (`KVB_API_BASE_URL`, `KVB_CLIENT_ID`, `KVB_CLIENT_SECRET`)

| Field | Value |
|---|---|
| **Env var names** | `KVB_API_BASE_URL`, `KVB_CLIENT_ID`, `KVB_CLIENT_SECRET` |
| **Where they are read** | `apps/api/app/config.py` lines 36–39; consumed by `apps/api/app/integrations/kvb_client.py` (OAuth2 client-credentials flow, real mode) |
| **Also in** | `apps/api/.env.example` lines 27–30; `docker-compose.yml` `api.environment` block lines 18–20; `render.yaml` `vetlink-api` (KVB_API_BASE_URL is `value: stub`; CLIENT_ID/SECRET are sync:false secrets) |
| **Where they come from** | **Kenya Veterinary Board** (KVB) IT department — **NOT obtainable yet**. KVB does not currently expose a public API |
| **Required for minimal deployment** | ❌ **Not obtainable yet — externally blocked.** Leave `KVB_API_BASE_URL` as `stub`; this is correct and intentional |

**Why it is blocked (not a coding gap):** the "verify a vet" feature runs against
a **temporary stub** returning canned data for a few fake licence numbers and
logging a WARNING on every call. Going live requires: KVB's IT department
exposing a public REST API + a formal data-sharing agreement under the **Data
Protection Act 2019**. This is a **partnership/government-process dependency
outside this project's control**.

**What this project needs from KVB (and nothing more):**
1. A public REST lookup endpoint — `GET {base}/api/v1/verify/{license_number}` →
   `{status, name, license_type}`.
2. OAuth2 client-credentials for VetLink254 (`KVB_CLIENT_ID`, `KVB_CLIENT_SECRET`).
3. The base URL (`KVB_API_BASE_URL`).

**What it explicitly does NOT ask for:** no bulk data export, no database
access, no role in licensing decisions. The full contract is the technical
document prepared for KVB's IT team: **`docs/KVB_INTEGRATION.md`**.

**When KVB becomes available:** set the three env vars (drop-in; no code
changes expected if the interface is respected), then delete the `_STUB_LICENSES`
dict + stub branch per `docs/KVB_INTEGRATION.md` §7. Until then, **leave the
stub in place** — it is the honest default.

---

## 9. `ACCESS_TOKEN_EXPIRE_MINUTES` (optional)

| Field | Value |
|---|---|
| **Env var name** | `ACCESS_TOKEN_EXPIRE_MINUTES` |
| **Where it is read** | `apps/api/app/config.py` line 24; used in `apps/api/app/core/security.py` line 50 (JWT lifetime) |
| **Also in** | `apps/api/.env.example` line 17 |
| **Required for minimal deployment** | ⚪ Optional — defaults to `1440` (24h). Lower it (e.g. `60`) if you want shorter-lived admin sessions |

---

## 10. `CORS_ORIGINS` (REQUIRED to set deliberately before production)

| Field | Value |
|---|---|
| **Env var name** | `CORS_ORIGINS` |
| **Where it is read** | `apps/api/app/config.py` line 29 + the `cors_origins_list` property (line 73); applied in `apps/api/app/main.py` CORS middleware |
| **Also in** | `apps/api/.env.example` line 20; `docker-compose.yml` `api.environment` block line 17; `render.yaml` `vetlink-api` has `value: "*"` |
| **Where it comes from** | You choose it — a comma-separated list of the web dashboard's public origin(s) |
| **Required for minimal deployment** | ⚠️ Required to **harden**; the default `*` works but is a documented dev/demo setting |

**What to set:** after the dashboard gets its public URL (§11.2), set
`CORS_ORIGINS` to that exact origin, e.g. `https://dashboard.vetlink254.co.ke`.
Multiple origins: `https://a.example,https://b.example`. This restricts browser
calls to the API to your own dashboard. **A real telecom USSD gateway never
needs CORS at all.**

---

## 11. The domain purchase + DNS (last, but start early — DNS propagates slowly)

Two public URLs are needed. **Start this early**: DNS changes can take hours.

### 11.1 API + USSD public URLs (the `api` service and its webhook)

| Field | Value |
|---|---|
| **What it is** | The public HTTPS address of the Core API (Render auto-assigns `https://vetlink-api.onrender.com` by default) |
| **Where it is referenced** | `render.yaml` `vetlink-ussd` env block → `API_BASE_URL` is currently the hardcoded `https://vetlink-api.onrender.com` (line 73). **You should change this to your real domain** (or keep the `.onrender.com` default) |
| **Where it comes from** | Render auto-generates it; you may point a custom domain at it |
| **Required** | ✅ Required — the ussd service must know where the API is |

**Custom domain for the API (optional but recommended):**
1. Buy a domain at any registrar (e.g. `vetlink254.co.ke` via a Kenyan registrar).
2. In Render → `vetlink-api` service → *Settings* → *Custom Domains* → add
   `api.vetlink254.co.ke`. Render gives you a `CNAME` target.
3. At your registrar, add a `CNAME` record: `api` → the Render target.
4. Wait for propagation; Render issues the TLS certificate automatically.

**USSD webhook note:** the telecom short code (§5.1) must point at a public
HTTPS `POST /ussd` URL. That endpoint lives on the **ussd** service. Give the
ussd service its own custom domain (`ussd.vetlink254.co.ke`) the same way, or
reuse the API's domain with a path — but the ussd service is the webhook host,
so it needs a public URL. (When you connect Africa's Talking USSD, you will
enter this URL as the callback.)

### 11.2 The dashboard public URL

| Field | Value |
|---|---|
| **What it is** | The public URL of the static verified-clinics dashboard |
| **Where it is referenced** | `apps/web/index.html` → `window.VETLINK_API_BASE` (line 40) — currently `http://localhost:8000` |
| **Where it comes from** | Render's static site (`vetlink-web`) auto-assigns a URL; set a custom domain (e.g. `dashboard.vetlink254.co.ke`) the same way as §11.1 |
| **Required** | ⚠️ Optional for the dashboard to exist; **required** for it to show live data from a real API |

**The one code edit at deploy time:** change
`apps/web/index.html` line 40 `window.VETLINK_API_BASE` from
`http://localhost:8000` to your deployed API origin (e.g.
`https://api.vetlink254.co.ke`) and commit. Then set `CORS_ORIGINS` (§10) to the
dashboard origin.

### 11.3 DNS summary table

| Hostname | Type | Value (from Render) | Used by |
|---|---|---|---|
| `api.vetlink254.co.ke` (example) | CNAME | Render `vetlink-api` target | Core API + `API_BASE_URL` for ussd |
| `ussd.vetlink254.co.ke` (example) | CNAME | Render `vetlink-ussd` target | USSD webhook for the telco short code |
| `dashboard.vetlink254.co.ke` (example) | CNAME | Render `vetlink-web` target | Dashboard + `CORS_ORIGINS` |

---

## 12. Master checklist (top to bottom, as a non-engineer would follow it)

1. ☐ **Create the Render account** and connect the `GafaNation1/VetLink254`
   GitHub repo (§1). Deploy the blueprint **once with no secrets** to confirm
   the infra comes up.
2. ☐ **Generate `SECRET_KEY`** and paste into Render `vetlink-api` (§2).
3. ☐ **Choose `ADMIN_EMAIL` / `ADMIN_PASSWORD`** and paste into Render
   `vetlink-api` (§3).
4. ☐ **Confirm `DATABASE_URL` / `REDIS_URL` are wired** (they are automatic —
   §4). Do not look for them.
5. ☐ **Buy the domain** and start DNS pointing now (§11 — it propagates slowly).
6. ☐ **Africa's Talking:** create the account, generate an API key, decide
   sandbox vs live, set `AT_USERNAME`/`AT_API_KEY`/`AT_SENDER_ID` on
   `vetlink-api` (§5). Separately, **start the short-code purchase** (§5.1) —
   long lead time.
7. ☐ **Cloudflare R2:** create the bucket + token, set all four (five) `R2_*`
   vars on `vetlink-api` (§6).
8. ☐ **`BOARD_NOTIFICATION_PHONE`** on `vetlink-api` (§7) — a real `+2547...`
   number.
9. ☐ **KVB:** nothing to do — it is externally blocked. Leave `stub`
   (`KVB_API_BASE_URL` stays `stub`; do not hunt for `KVB_CLIENT_*` yet). See
   §8 + `docs/KVB_INTEGRATION.md`.
10. ☐ **Dashboard:** edit `apps/web/index.html` `window.VETLINK_API_BASE` to
    the API origin, commit, and set `CORS_ORIGINS` to the dashboard origin (§10,
    §11.2).
11. ☐ **USSD webhook:** point the short code's callback at the ussd service's
    public HTTPS `POST /ussd` URL; confirm `API_BASE_URL` on the ussd service
    (§11.1).
12. ☐ **Verify each switch flipped live** — for each credential you set,
    confirm the corresponding row in `docs/CURRENT_STATE.md` §4 moves from
    "pending <credential>" to "live" (re-run the live checks in §2/§5 of that
    document).

### 12.1 The auto-provided / non-credential items (so you don't hunt for them)

- `DATABASE_URL` — auto from Render Postgres (§4)
- `REDIS_URL` — auto from Render Redis (§4)
- `ENVIRONMENT` — already set to `production` in `render.yaml` (not a secret)
- `KVB_CACHE_TTL_SECONDS` — already `180` in `render.yaml` (not a secret)
- `LOCAL_UPLOAD_DIR` / `DOC_UPLOAD_MAX_MB` — already set in `render.yaml`
  (`/app/uploads` / `10`) — only relevant when R2 is unset
- `SESSION_TTL_SECONDS` — already `180` on the ussd service (not a secret)
- `KVB_API_BASE_URL` — **keep** `stub` until KVB is live (§8)

---

## 13. Known deployment caveats (from the Part-1 audit of this session)

1. **render.yaml no longer declares a `startCommand`/`preDeployCommand`.**
   During the 2026-08-20 demo pass a later fix commit (`7fcc0f9`, "align docker
   startup command for render deployment") **removed** the `startCommand` and
   `preDeployCommand` keys from `render.yaml`, and `render.yaml` now relies on
   the Dockerfiles' `CMD` (uvicorn/gunicorn/http.server). **Consequence:** the
   api container will start uvicorn directly, but `alembic upgrade head` and
   `python -m scripts.create_admin` will **NOT** run automatically on Render
   (they are only in the docker-compose `command:`). On a fresh Render deploy
   the schema will be empty and no admin will be seeded until you run the
   migration+seed manually (via Render → api service → *Shell*:
   `alembic upgrade head && python -m scripts.create_admin`). **This was
   flagged rather than edited** per the session constraint; before going live,
   either (a) re-add a `preDeployCommand: alembic upgrade head && python -m
   scripts.create_admin` to `render.yaml`'s api service, or (b) plan to run it
   once in the Render shell after the first deploy. This is the **one**
   deployment step that is not yet purely "paste a credential".
2. **`apps/api/.env.example` has dev-placeholder admin creds** — harmless as a
   template, but make sure real values override them in Render (Render env vars
   take precedence over the file).
3. **CORS default `*`** — set `CORS_ORIGINS` deliberately (§10) before any
   production traffic.
4. **The USSD `/simulate` dev sandbox is unauthenticated** — it is fine on
   localhost, but a production-exposed `/simulate` would let anyone walk a menu.
   The production `POST /ussd` webhook is the real entry point; consider
   disabling `/simulate` (or protecting it) before going live.

---

*This document is the operational companion to `docs/KVB_INTEGRATION.md`
(KVB contract) and `docs/CURRENT_STATE.md` (what is live / code-complete /
stub). Created 2026-08-21 as Part 3 of the deployment-readiness session.*