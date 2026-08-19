# apps/web — Public verified-clinics dashboard (read-only)

A deliberately minimal, read-only public page that lists **verified** VetLink254 clinics
(name, county, services, unique code). It is a credibility signal for investors/partners — not the
full farmer/clinic/admin website (that remains future scope per `docs/architecture.md`).

**Stack choice (logged):** plain HTML/CSS/JS, zero build step, zero framework. Served by a 4-line
`Dockerfile` (`python -m http.server`). No login, no write calls.

## How it gets its data

`app.js` fetches `GET /api/v1/clinics/` from the Core API and renders only clinics whose
`verification_status == "verified"` (the endpoint is public by design). The API base URL is set in
`index.html` as `window.VETLINK_API_BASE`:

- Local docker-compose demo → `http://localhost:8000` (the api service port).
- Same-origin proxy / future production → `""` (relative `/api/v1`).
- Render static site → the deployed API domain.

The API must allow the browser origin via `CORS_ORIGINS` (dev default `*`; restrict before production).

## Run locally

With the full stack: `docker compose up --build -d`, then open `http://localhost:8002`.
Or standalone: `python3 -m http.server 8002` from this folder.

> Note: clinics only appear once they have been approved through the KYC flow
> (`POST /api/v1/clinics/{id}/verify` as an admin), so a fresh database shows an empty state until
> then.