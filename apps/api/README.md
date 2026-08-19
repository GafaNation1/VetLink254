<!-- apps/api/README.md — Documentation and entrypoint reference for VetLink254 Core API -->
# VetLink254 Core API

Core FastAPI backend for VetLink254 powering business logic, user management, clinic listings, bookings, wallets, and payments.

## Quick Start

```bash
docker-compose up --build
```

Healthcheck: `GET http://localhost:8000/health`
OpenAPI docs: `GET http://localhost:8000/docs`

## Tests

The test suite runs against an **isolated SQLite test database** (see `tests/conftest.py`)
and does **not** require the docker-compose stack (no Postgres/Redis needed).

Run from the `apps/api` directory (single command; runs in a throwaway
`python:3.11-slim` container matching the production Dockerfile):

```bash
docker run --rm -v "$PWD":/app -w /app \
  -e COVERAGE_FILE=/tmp/.coverage -e PYTHONDONTWRITEBYTECODE=1 \
  python:3.11-slim sh -c \
  "pip install --quiet -r requirements.txt && python -m pytest tests/ -p no:cacheprovider --cov=app --cov-report=term-missing"
```

Or run both apps' suites together from the repo root with `./run_tests.sh`.

Notes:
- `DATABASE_URL` is overridden inside `tests/conftest.py` to a temp SQLite file
  before the app is imported, so the whole suite is self-contained.
- `pytest`/`pytest-cov`/`httpx` are in `requirements.txt` (httpx is required by
  FastAPI's `TestClient`). If you'd rather keep test deps out of the runtime image,
  move them to a separate `requirements-dev.txt` later.
- `COVERAGE_FILE=/tmp/.coverage` writes coverage data inside the container (avoids slow
  writes to some host mounts); `PYTHONDONTWRITEBYTECODE=1` + `-p no:cacheprovider` keep
  the app directory free of `.pyc`/`.pytest_cache` artifacts after a run.
- Known behavior differences vs Postgres are logged in `docs/progress/LOG.md`.
