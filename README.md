# VetLink254

National veterinary-connect platform: **one FastAPI Core API** (`apps/api`) reached through
**two front doors** — a **USSD adapter** (`apps/ussd`, Flask) for feature-phone farmers and a
**public web dashboard** (`apps/web`, plain HTML/CSS/JS) listing verified clinics.

## What it does

- Farmers dial a USSD short code, pick a language (English / Kiswahili), and search for a vet by
  animal, service (~24-item catalogue), and county (type-to-search over all 47 counties) — then get
  the nearest **verified** clinic with distance and a unique code.
- Farmers can **verify a vet** by KVB license number (currently a documented **stub** — the real KVB
  API is externally blocked, see `docs/CURRENT_STATE.md` §5.12).
- Clinics register and submit **KYC documents** (multipart upload: PNG/JPEG/WebP/PDF, ≤10 MB) which an
  admin reviews; approval issues a `VL254-<region>-<seq>` unique code.
- The **dashboard** (http://localhost:8002) publicly lists verified clinics.

## Architecture discipline

The USSD adapter contains **no business logic**: it walks a declarative menu tree, keeps session
state in Redis, and delegates matching / license verification / SMS notifications to the Core API
over HTTP. The API owns all data and logic. See `docs/architecture.md`.

## Quick start (local, via Docker Compose)

```bash
docker compose up --build -d        # starts api(:8000), ussd(:8001), web(:8002), postgres, redis
```

On first boot the api runs `alembic upgrade head` and seeds the admin account from
`ADMIN_EMAIL` / `ADMIN_PASSWORD` (dev default `admin@vetlink254.local` / `dev-admin-password-change-me` —
**change before any real deployment**).

Full walkthrough (create clinic → upload KYC → approve → match → USSD find-a-vet): see
`docs/CURRENT_STATE.md` §6.3.

## Tests

```bash
./run_tests.sh    # both pytest suites in throwaway python:3.11-slim containers (needs Docker)
```

- `apps/api`: 138 tests, ~96% coverage
- `apps/ussd`: 73 tests

CI (`.github/workflows/ci.yml`) runs the same suite + docker builds on every push to `main` and PR.

## Deployment status

| Piece | State |
|---|---|
| `render.yaml` (api + ussd + static dashboard + Postgres + Redis) | **Code complete, not yet deployed** — pending a Render account + the `sync:false` secrets (AT_*, ADMIN_*, R2_*, SECRET_KEY, BOARD_NOTIFICATION_PHONE) |
| SMS (Africa's Talking SDK wired) | **Code complete, not yet live-verified** — pending `AT_USERNAME` / `AT_API_KEY` |
| USSD short code + public HTTPS webhook | **Not provisioned** — `/simulate` + `POST /ussd` sandbox only |
| KYC file storage | **Local disk live; Cloudflare R2 code complete** — pending R2 credentials |
| KVB license verification | **Stub only** — externally blocked (no public KVB API yet) |

Nothing in the table above is claimed to be live; each piece is marked honestly as
"code complete, not yet live-verified — pending <credential>" in `docs/CURRENT_STATE.md`.

## Docs

- `docs/CURRENT_STATE.md` — **read this first**: exact folder tree, what works, what's stubbed, how to run everything
- `docs/architecture.md` — original product vision / engineering blueprint
- `docs/progress/LOG.md` — session-by-session build history
- `docs/progress/STATUS.md` — living one-glance snapshot