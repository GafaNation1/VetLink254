# KVB Integration Contract — VetLink254 → Kenya Veterinary Board license verification

Status: **STUB / not live.** This document is the agreed *contract* between VetLink254 and the
Kenya Veterinary Board (KVB) license-verification bridge. Today the KVB client ships in a temporary
stub mode; this contract defines exactly what must hold when KVB exposes a public API, so going
live is a config-only change (no code changes if the interface is respected).

**Source of truth:** KVB is the statutory authority on who holds a valid veterinary licence.
VetLink254 is NOT the source of truth, does NOT decide or persist license status, and never stores
it in Postgres. VetLink254 is a B2C bridge: a farmer can check a vet's license before trusting them.

---

## 1. Responsibilities / boundaries

- `apps/api/app/integrations/kvb_client.py` — the ONLY place that talks to KVB. Exposes ONE public
  method: `verify_license(license_number) -> {status, name, license_type}`.
- `apps/api/app/api/v1/kvb.py` — `GET /api/v1/verify-license`, the farmer-facing HTTP endpoint
  (deliberately PUBLIC — a read-only lookup; no admin token).
- `apps/ussd/app/api_client.py` — the USSD adapter forwards the typed number to apps/api and renders
  the answer. No licensing logic lives in the adapter.
- The internal clinic-onboarding verification (`/api/v1/clinics/{id}/verify`) is a **different**
  concept and is deliberately NOT connected to KVB license status.

## 2. Auth — OAuth2 client-credentials (assumed, to confirm)

- Token endpoint: `POST {KVB_API_BASE_URL}/oauth/token`
- Body (form-encoded): `grant_type=client_credentials`, `client_id`, `client_secret`
- Response: `{"access_token": "..."}` (bearer token)
- Every subsequent KVB call sends `Authorization: Bearer <token>`.
- Credentials come from env: `KVB_CLIENT_ID`, `KVB_CLIENT_SECRET`.

## 3. Lookup endpoint (assumed, to confirm)

- `GET {KVB_API_BASE_URL}/api/v1/verify/{license_number}`
- Auth: `Authorization: Bearer <token>`
- Success `200`:
  ```json
  {
    "status": "active",
    "name": "Dr. Wanjiku Kamau",
    "license_type": "Veterinary Surgeon"
  }
  ```
  - `status` is `"active"` when the vet is currently licensed; any other value (e.g. `"expired"`)
    means NOT currently verified.
- `404` → no record for this license number → VetLink254 surfaces "No vet registered with this
  KVB license number" (END screen).
- Any other HTTP status or a missing `status`/`name`/`license_type` key → `KVBVerificationError` →
  `502` on the API.

## 4. Error mapping (through the stack)

| KVB behaviour          | kvb_client raises       | apps/api returns | USSD shows                                      |
|------------------------|-------------------------|------------------|-------------------------------------------------|
| 404 (no record)        | `KVBNotFoundError`      | `404`            | "No vet is registered with KVB license number…" |
| transport / auth / 5xx | `KVBVerificationError`  | `502`            | "Service temporarily unavailable…"              |
| blank input            | `KVBVerificationError`  | `502`            | "Service temporarily unavailable…"              |

## 5. Caching

- Successful lookups cached in Redis per-session only, TTL = `KVB_CACHE_TTL_SECONDS` (default 180s,
  matching the USSD session TTL — a cached license status can never outlive the session it was
  fetched in). `<= 0` disables caching.
- Errors / not-found are NEVER cached.
- Results are NEVER persisted to Postgres. License status is always re-checked live per session.
- Redis unreachable → degrade to an uncached live call with a WARNING (never a failure).

## 6. Stub mode (current behaviour)

`KVB_API_BASE_URL` unset or `"stub"` selects stub mode:

- Canned dataset in `kvb_client.py::_STUB_LICENSES`:
  - `KVB-1001` → `active` (Dr. Wanjiku Kamau, Veterinary Surgeon)
  - `KVB-1002` → `active` (Dr. Brian Otieno, Veterinary Surgeon)
  - `KVB-1003` → `expired` (Dr. Grace Muthoni, Veterinary Surgeon)
- Every stub call logs a WARNING so it can never be mistaken for a real integration.
- Any other number → `KVBNotFoundError`.

## 7. Going live (config-only checklist)

1. Confirm the assumed token + lookup endpoint shapes against KVB's real API; adjust
   `_http_fetch`/`_fetch_access_token` if the real shapes differ (interface stays the same).
2. Set `KVB_API_BASE_URL` to the real endpoint.
3. Set real `KVB_CLIENT_ID` / `KVB_CLIENT_SECRET`.
4. (Recommended) set `KVB_CACHE_TTL_SECONDS`.
5. Delete the `_STUB_LICENSES` dict and stub branch once the real API is verified.
6. No changes needed in the USSD adapter or the `/verify-license` endpoint.

## 8. Related: board notification on lookup

Per task 15, `GET /api/v1/verify-license` also sends the board a fire-and-forget SMS on each lookup
(`notify_board` query param, default `true`, gated by `BOARD_NOTIFICATION_PHONE`). This is a
documented stopgap; see `docs/progress/LOG.md`.