# Secure Login System — FOSSEE Osdag Screening Task

Two independent implementations of a login/registration/logout system with per-user file isolation, built for the FOSSEE Osdag Autumn Semester Internship 2026 screening task:

1. **Custom backend** — Django + Django REST Framework + PostgreSQL + JWT
2. **Managed backend** — Appwrite (Auth, Databases, Storage)

Both implementations expose the same functional surface (register, login, logout, `/me`, `/files`, `/files/:id`) and are tested against the single provided `frontend/index.html` client, used unmodified as required by the task.

## Demo Video

Watch the full walkthrough: [Secure Login System — Demo](https://youtu.be/zEI10ti5QUo)

---

## Table of Contents

- [Demo Video](#demo-video)
- [Repository Structure](#repository-structure)
- [Quick Start](#quick-start)
- [Setup — Django Backend](#setup--django-backend)
- [Setup — Appwrite Backend](#setup--appwrite-backend)
- [Running the Frontend](#running-the-frontend)
- [Seeded Test Users](#seeded-test-users)
- [Running Tests](#running-tests)
- [Design Reasoning](#design-reasoning)
  - [JWT vs. Session-Based Authentication](#jwt-vs-session-based-authentication)
  - [How Logout Works Internally](#how-logout-works-internally)
  - [How User Data Isolation Is Enforced](#how-user-data-isolation-is-enforced)
  - [Appwrite: Automatic vs. Configured](#appwrite-automatic-vs-configured)
- [Future Improvements](#future-improvements)

---

## Repository Structure

```
secure-login-system/
├── custom-backend-django/     # Implementation 1 — Django + DRF + PostgreSQL
│   ├── config/                 # project settings, URL root
│   ├── accounts/                # auth, user model, seed command
│   ├── files/                   # file model, list/detail/download views
│   ├── tests/                   # pytest suite
│   └── requirements.txt
│
├── appwrite-backend/           # Implementation 2 — Appwrite
│   └── seed.py                  # Server SDK seed script
│
├── frontend/                   # Provided testing client (adapter shipped alongside it)
│   ├── index.html
│   ├── mock-api.js
│   ├── appwrite-adapter.js      # Web SDK adapter consumed by frontend/index.html
│   └── seed-data.json
│
└── README.md
```

---

## Quick Start

```bash
git clone https://github.com/captain-07/secure-login-system.git
cd osdag-secure-login-system

# Django backend
cd custom-backend-django
python -m venv venv && source venv/bin/activate   # venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env        # fill in DB credentials, SECRET_KEY
python manage.py migrate
python manage.py seed_users
python manage.py runserver

# In a separate terminal — serve the frontend
cd ../frontend
python -m http.server 5500
```

Open `http://localhost:5500/index.html`, select **Custom REST backend**, set Base URL to `http://localhost:8000/api`, and log in with any seeded user below.

---

## Setup — Django Backend

### Prerequisites
- Python 3.11+
- PostgreSQL (running locally or reachable via `DATABASE_URL`)
- Redis (used for the JWT logout blocklist — see [How Logout Works Internally](#how-logout-works-internally))

### Steps

```bash
cd custom-backend-django
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```env
DB_NAME=osdag_login
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
REDIS_URL=redis://localhost:6379/1
SECRET_KEY=change-me
DEBUG=True
```

```bash
python manage.py migrate
python manage.py seed_users     # creates alice, bob, carol + sample files
python manage.py runserver      # http://localhost:8000
```

Verify Redis is reachable before testing logout:

```bash
redis-cli ping   # should return PONG
```

---

## Setup — Appwrite Backend

### 1. Console configuration

1. Create a project at [cloud.appwrite.io](https://cloud.appwrite.io).
2. **Auth → Settings**: confirm the Email/Password method is enabled.
3. **Databases**: create a database, then a `files` collection with attributes:

   | Attribute | Type | Required |
   |---|---|---|
   | `ownerId` | String (64) | Yes |
   | `filename` | String (255) | Yes |
   | `mimeType` | String (100) | No |
   | `sizeBytes` | Integer | No |
   | `storageFileId` | String (64) | Yes |

   Leave collection-level permissions empty — isolation is enforced per-document (see [Appwrite: Automatic vs. Configured](#appwrite-automatic-vs-configured)).

   Add an index on `ownerId` (Key type, Ascending) — `GET /files` filters rows with `Query.equal("ownerId", ...)`, which Appwrite refuses to run without a matching index.
4. **Storage**: create a bucket (`user-files`), same per-file permission model.
5. **Settings → Platforms**: add a Web Platform with hostname `localhost` (Appwrite enforces CORS at the project level; this step is required even in local development).
6. **Settings → API Keys**: create a Server API key with `users.write`, `databases.write`, `files.write` scopes — used only by the seed script, never exposed to the browser.

### 2. Seed the data

```bash
cd appwrite-backend
cp .env.example .env        # fill in project ID, database ID, collection ID, bucket ID, API key
pip install appwrite --break-system-packages
python seed.py
```

---

## Running the Frontend

The provided `frontend/index.html` must be served over `http://`, not opened as a `file://` path — the Appwrite Web SDK rejects `file://` origins outright.

```bash
cd frontend
python -m http.server 5500
```

Open `http://localhost:5500/index.html` and select a backend mode:

| Mode | Configuration |
|---|---|
| **Custom REST backend** | Base URL: `http://localhost:8000/api`. Leave "uses cookie sessions" unchecked — this backend is bearer-token based. |
| **Appwrite** | Fill in Endpoint, Project ID, Database ID, Files Collection ID, and Bucket ID from your Appwrite Console. |
| **Mock** | No backend required — demonstrates expected client behavior only, per the task's note that `mock-api.js` is not a reference implementation. |

---

## Seeded Test Users

Both backends seed the same three accounts:

| Email | Password |
|---|---|
| `alice@example.com` | `Password123!` |
| `bob@example.com` | `Password123!` |
| `carol@example.com` | `Password123!` |

Each user has 2 sample files. Cross-account access (e.g. Alice requesting one of Bob's file IDs) is expected to fail — see [How User Data Isolation Is Enforced](#how-user-data-isolation-is-enforced) for the exact failure modes per backend.

---

## Running Tests

```bash
cd custom-backend-django
pytest
```

The suite covers registration, login (including the generic-error and lockout requirements), logout and token blocklisting, `/me` isolation, `/files` and `/files/:id` isolation (including the 403-vs-404 distinction), and login rate limiting. Tests use an in-memory cache fixture, so Redis does not need to be running to execute them — only PostgreSQL is required, for Django's test database.

The Appwrite backend is verified manually against the console and the frontend client, since its isolation guarantees are enforced by Appwrite's permission engine rather than application code — see below.

---

## Design Reasoning

### JWT vs. Session-Based Authentication

**Decision: JWT (short-lived access token + rotating refresh token), not server-side sessions.**

Django's session framework would make server-side logout invalidation trivial — a session row can simply be deleted. I chose JWT instead because it more directly demonstrates the token-lifecycle reasoning relevant to the backend roles I'm targeting (fintech and B2B SaaS), where JWT-based auth with explicit revocation is the norm, and because the project already depends on Redis for the revocation mechanism below.

The tradeoff is real: a JWT is self-contained and remains cryptographically valid until it expires, regardless of server-side state. Satisfying "logout invalidates server-side, not just client-side" therefore requires an explicit revocation layer — described next — rather than getting it for free the way a session-based design would.

### How Logout Works Internally

Logout performs two independent actions:

1. **Refresh token blacklisting.** The refresh token is blacklisted using `djangorestframework-simplejwt`'s built-in `token_blacklist` app, preventing it from being used to mint new access tokens.
2. **Access token blocklisting.** The current access token's `jti` (unique token identifier) is written to Redis with a TTL equal to the token's remaining lifetime. A custom authentication class, `BlocklistAwareJWTAuthentication`, checks Redis for this `jti` on every subsequent request — before trusting an otherwise cryptographically valid signature — and rejects the request if found.

Blacklisting only the refresh token would leave a window (up to the 15-minute access token lifetime) during which a captured access token remains usable after "logout." The Redis blocklist closes that window immediately. Using Redis specifically — rather than a database table — means blocklist entries expire on their own via TTL, with no cleanup job required.

### How User Data Isolation Is Enforced

**Django backend:**

- `GET /me` returns `request.user`, derived solely from the validated token. No route or query parameter accepts a user identifier, so there is no path through which a different user's profile could be requested.
- `GET /files` filters at the database level — `File.objects.filter(owner=request.user)` — so rows belonging to other users are never returned, rather than being fetched and filtered afterward.
- `GET /files/:id` looks up the file by ID with no owner filter in the initial query, then explicitly compares `file.owner` against `request.user`. A nonexistent ID returns `404`; an ID that exists but belongs to a different user returns `403`.

This 403/404 split is a deliberate design decision worth stating explicitly. General REST security convention favors returning an identical `404` for both cases, to prevent an attacker from enumerating valid file IDs by observing which ones return a different status. However, the task specification explicitly requires a response "distinct from a file that simply does not exist" — a direct requirement for the 403/404 distinction implemented here. I'm noting this tension rather than silently resolving it, since it reflects a genuine tradeoff between a general security convention and an explicit task requirement; I followed the latter.

**Appwrite backend:**

Isolation is enforced by Appwrite's permission engine, not application code. Each file's storage object and metadata document is created with a `read(user:<ownerId>)` permission scoped to exactly one user, set at creation time in `seed.py`. A request for another user's file is rejected by Appwrite itself before any of my code runs. One consequence worth flagging: Appwrite surfaces this as `401` (exists, not yours) versus `404` (doesn't exist) — a different status code from the Django backend's `403`/`404` split, but the same underlying distinction. The difference reflects how each platform's permission model surfaces a denial, and is documented here rather than forced to match artificially.

### Appwrite: Automatic vs. Configured

**Handled automatically by Appwrite:**
- Password hashing and secure storage
- Session issuance and server-side invalidation (`account.deleteSession("current")`)
- Generic "invalid credentials" response for both wrong-password and unknown-email cases

**Configured explicitly:**
- The `files` collection schema and its attributes
- Per-document and per-file `read(user:<ownerId>)` permissions, set individually at creation time — this is the mechanism that actually enforces isolation, not a query filter written in application code
- The storage bucket and its matching per-file permission pattern
- The Web Platform / CORS registration required for the browser client to reach the project at all

---

## Future Improvements

- Move from `AbstractUser` to a from-scratch `AbstractBaseUser` implementation for full control over the user model, rather than inheriting Django's default admin/permission scaffolding, which exceeds what this task strictly needs.
- Add a "list active sessions / revoke a specific device" endpoint — meaningful now that refresh tokens are individually blacklistable, and a natural extension of the existing revocation mechanism.
- Add TOTP-based two-factor authentication as an optional login step.
- Replace seeded dummy file content with realistic sample files (PDFs, images) for a more representative download-testing experience.
- Add CI (GitHub Actions) to run the pytest suite on every push. Not yet wired up due to time constraints, but the test suite was written with this in mind and requires no changes to support it.