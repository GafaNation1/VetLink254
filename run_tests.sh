#!/usr/bin/env bash
# run_tests.sh — run the FULL VetLink254 test suite (apps/api + apps/ussd) with a single command.
# Uses throwaway python:3.11-slim containers (matches the project Dockerfiles) — the docker-compose
# stack does NOT need to be running. Each app spins up its own isolated test fixtures (SQLite for
# the API, in-memory/fakeredis session stores for USSD). No Postgres/Redis required.
# A named `vetlink_pip_cache` volume is used so repeated runs don't re-download packages.
#
# Usage:  ./run_tests.sh        (from the repo root)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$REPO_DIR/apps/api"
USSD_DIR="$REPO_DIR/apps/ussd"
PIP_CACHE="vetlink_pip_cache"

docker volume create "$PIP_CACHE" >/dev/null 2>&1 || true

echo "==> VetLink254 test suite"
echo

echo "==> apps/api tests (Core API — SQLite test DB)"
docker run --rm -v "$PIP_CACHE:/root/.cache/pip" -v "$API_DIR:/app" -w /app \
  -e COVERAGE_FILE=/tmp/.coverage -e PYTHONDONTWRITEBYTECODE=1 \
  python:3.11-slim sh -c \
  "pip install --quiet -r requirements.txt && python -m pytest tests/ -p no:cacheprovider --cov=app --cov-report=term"
echo

echo "==> apps/ussd tests (USSD thin adapter — in-memory store + mocked api_client)"
docker run --rm -v "$PIP_CACHE:/root/.cache/pip" -v "$USSD_DIR:/app" -w /app \
  -e PYTHONDONTWRITEBYTECODE=1 \
  python:3.11-slim sh -c \
  "pip install --quiet -r requirements.txt && python -m pytest tests/ -p no:cacheprovider"
echo

echo "==> All VetLink254 tests passed."
