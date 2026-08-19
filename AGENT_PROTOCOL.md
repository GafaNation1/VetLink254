# VetLink254 — Build Protocol & Step 1

This file has two parts:
1. **The Documentation Protocol** — paste this into any agent (opencode, Cursor, Devin, Codex, whatever) at the start of every session. It forces the agent to leave a trail that the *next* agent — possibly a different model entirely — can pick up cold.
2. **Step 1** — the actual first task to hand the agent.

Keep this file at the repo root as `AGENT_PROTOCOL.md`. Every agent you use should be told to read it first.

---

## PART 1 — Documentation Protocol (give this to every agent, every time)

```
You are working on the VetLink254 codebase. Before writing any code, read
/docs/architecture.md and /docs/progress/LOG.md in full.

Strict rules for this session:

1. LOG EVERY STEP. Before you touch any file, append an entry to
   /docs/progress/LOG.md in this exact format:

   ## [YYYY-MM-DD] <short task title>
   - Model/agent: <your model name>
   - Goal: <one sentence, what this step accomplishes>
   - Files created: <list>
   - Files modified: <list>
   - Key decisions made: <anything a future agent needs to know to not
     redo or contradict this — e.g. "chose FastAPI over Flask for
     apps/api because of async webhook needs">
   - How to verify it works: <exact command(s) to run>
   - Known gaps / not done yet: <be honest, this is what saves the next
     agent time>

2. NEVER invent architecture. If a decision isn't already in
   /docs/architecture.md, propose it in the log entry under "Key
   decisions made" — don't just silently pick one and move on.

3. ONE SECTION AT A TIME. Only build what the current task asks for.
   Do not scaffold ahead into folders/features not yet requested — this
   keeps each step reviewable and keeps the log accurate.

4. every file you create must have a one-line comment at the top stating
   its purpose, e.g. `# services/matching_engine.py — finds nearest
   verified clinic for a given booking request`.

5. If you install a dependency, add it to the relevant requirements.txt
   / package.json AND note it in the log entry — never a silent install.

6. If you get stuck or make an assumption because something was
   ambiguous, write that assumption explicitly in the log. Do not guess
   silently.

7. At the end of the session, update /docs/progress/STATUS.md — a short
   living summary (not a log, a snapshot) of: what's built, what's next,
   what's broken. This is the file a brand-new agent reads first to get
   oriented in under a minute.
```

This protocol matters more than usual for you specifically because you're planning to swap agents when one stops working — the log is what makes that swap cost you minutes instead of days.

---

## PART 2 — Step 1: Repo Skeleton + `apps/api` Foundation

This is the very first task. Don't let the agent do anything beyond this scope yet.

**Task to give the agent:**

```
Set up the VetLink254 monorepo skeleton and the foundation of apps/api
ONLY. Do not build apps/ussd or apps/web yet — those are later steps.

1. Create the folder structure exactly as described in
   /docs/architecture.md Section 7 (create empty apps/ussd and apps/web
   folders with just a placeholder README in each, so the skeleton
   exists, but put no code in them yet).

2. In apps/api, set up:
   - A working FastAPI app (app/main.py) that runs and responds to a
     GET /health endpoint.
   - app/core/database.py — SQLAlchemy engine + session setup, reading
     a DATABASE_URL from environment variables (use a .env.example
     file, never commit real credentials).
   - app/models/ with THREE models only for now: User, Clinic, Booking
     — matching the fields in /docs/architecture.md Section 6. Leave
     the rest of the tables (wallet_transactions, payments, etc.) for
     a later step.
   - Alembic set up and one initial migration that creates these three
     tables.
   - app/api/v1/ with a bare-bones router file per model (users.py,
     clinics.py, bookings.py) — just a GET list endpoint and a POST
     create endpoint for each, no auth yet, no business logic yet.
   - requirements.txt with pinned versions.
   - docker-compose.yml at repo root that spins up: the api service,
     a postgres container, and a redis container (redis unused for now,
     but present since Step 2+ will need it).

3. Confirm it works by running docker-compose up and hitting:
   - GET /health
   - POST /api/v1/clinics with a sample payload
   - GET /api/v1/clinics and see it returned

4. Do the full logging protocol from Part 1 of AGENT_PROTOCOL.md —
   log this as your first entry in /docs/progress/LOG.md, and create
   /docs/progress/STATUS.md summarizing what now exists.

Stop after this. Do not proceed to registration logic, matching engine,
wallet, or USSD — those are separate steps we'll do one at a time.
```

**Why this is the right first step, not something else:** everything in the architecture — matching, wallet, USSD, website — depends on `users`, `clinics`, and `bookings` existing and being reachable over an API. Building this first, and *only* this, gives you a working skeleton you can actually run and test before any agent adds complexity on top of it. It also gives the documentation protocol its first real workout while the codebase is still small enough that a bad log entry is easy to spot and fix.

**What to check before moving to Step 2:** you should be able to run `docker-compose up`, hit the three endpoints with something like Postman or curl, and see data land in Postgres. If that works, come back and we'll do Step 2 — likely fleshing out the `clinics` verification fields and the document-upload path, or standing up the matching engine, whichever you want to prioritize.
