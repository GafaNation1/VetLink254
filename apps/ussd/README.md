<!-- apps/ussd/README.md — Thin USSD adapter service for VetLink254 -->
# USSD Service Adapter

Thin adapter (Flask) that receives telecom USSD webhooks and walks a declarative
menu tree for the **Find a Vet** flow. It holds **no business logic**: session state
lives in Redis, and nearest-clinic matching is delegated to `apps/api` over HTTP
(`GET /api/v1/match`). See `/docs/architecture.md` Section 3.2 / 7 and
`/docs/progress/LOG.md` for design decisions.

## Structure
- `app/main.py` — webhook receiver (`POST /ussd`) + local `/simulate` sandbox + `/health`
- `app/session_store.py` — Redis-backed session state (node + collected choices, 3-min TTL)
- `app/menu_tree.py` — declarative menu nodes: Language (EN/SW) → Welcome → Find a vet (animal → paginated service → 47-county type-to-search → sub-location → results) and Verify a vet (free-text license number → live KVB status via apps/api)
- `app/api_client.py` — thin HTTP client for `apps/api` (match / verify-license / notify); never queries the DB or SMS directly

## Run
`docker-compose up --build -d` from the repo root starts `ussd` on port `8001`.

## Simulate (no telecom needed)
The FIRST screen asks for a language (`1` English, `2` Kiswahili); the county step is
type-to-search (e.g. `nai` → `1. Nairobi`) and services are paginated (`#` = more options).
```
curl "http://localhost:8001/simulate?session_id=test1&text="
curl "http://localhost:8001/simulate?session_id=test1&text=1"
curl "http://localhost:8001/simulate?session_id=test1&text=1*1"
curl "http://localhost:8001/simulate?session_id=test1&text=1*1*1"
curl "http://localhost:8001/simulate?session_id=test1&text=1*1*1*1"
curl "http://localhost:8001/simulate?session_id=test1&text=1*1*1*1*nai"
curl "http://localhost:8001/simulate?session_id=test1&text=1*1*1*1*nai*1"
curl "http://localhost:8001/simulate?session_id=test1&text=1*1*1*1*nai*1*Kilimani"
curl "http://localhost:8001/simulate?session_id=test1&text=1*1*1*1*nai*1*Kilimani*1"
```

**Verify a vet** (option 2 — license status is looked up live via `GET /api/v1/verify-license`
against the KVB STUB by default, see `docs/CURRENT_STATE.md` §2.12):
```
curl "http://localhost:8001/simulate?session_id=verify1&text="
curl "http://localhost:8001/simulate?session_id=verify1&text=1"
curl "http://localhost:8001/simulate?session_id=verify1&text=1*2"
curl "http://localhost:8001/simulate?session_id=verify1&text=1*2*KVB-1001"
```

## Tests

The USSD test suite needs **no Redis server and no live apps/api** — the
session store is an in-memory stand-in (with the real `RedisSessionStore`
also tested against `fakeredis`) and `api_client.match_clinics` is mocked.

Run from the `apps/ussd` directory (single command; runs in a throwaway
`python:3.11-slim` container matching the production Dockerfile):

```bash
docker run --rm -v "$PWD":/app -w /app -e PYTHONDONTWRITEBYTECODE=1 \
  python:3.11-slim sh -c \
  "pip install --quiet -r requirements.txt && python -m pytest tests/ -p no:cacheprovider"
```

Or run both apps' suites together from the repo root with `./run_tests.sh`.

Notes:
- `pytest` and `fakeredis` are in `requirements.txt` (test-only deps; move to a
  `requirements-dev.txt` if you want them out of the runtime image).
- `fakeredis` stands in for a Redis server when testing `RedisSessionStore`;
  the flow tests exercise `app.main.handle_request` with an in-memory store.
- `PYTHONDONTWRITEBYTECODE=1` + `-p no:cacheprovider` keep the app directory free of
  `.pyc`/`.pytest_cache` artifacts after a run.