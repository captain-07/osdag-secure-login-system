# login-system

A login system with two interchangeable backends: a custom Django REST API and an Appwrite-based backend. A static frontend (vanilla JS) can run against either, or against an in-browser mock.

## Project structure

```
login-system/
├── custom-backend-django/   # Django REST API (auth + file management)
├── appwrite-backend/        # Appwrite seed + adapter (alternative backend)
├── frontend/                # Static frontend (index.html + mock API)
├── report/                  # Final report (report.pdf)
└── screenshots/             # UI screenshots
```

## custom-backend-django

Django REST Framework API using PostgreSQL and Redis:

- `accounts/` — custom email-based user model, JWT auth (simplejwt + Redis blocklist), login throttling, account lockout, and a `seed_users` management command.
- `files/` — per-user file list/detail/download endpoints with strict ownership checks.
- `tests/` — pytest suite (`test_auth`, `test_logout`, `test_files`, `test_throttle`). Shared fixtures live in `conftest.py`; the test run automatically uses SQLite + in-memory cache so no external services are needed.

### Setup

```bash
cd custom-backend-django
cp .env.example .env          # then fill in DB / Redis values
python -m venv venv           # or use the repo-level venv
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_users   # creates alice/bob/carol@example.com
python manage.py runserver
```

### Run tests

```bash
cd custom-backend-django
pytest
```

## appwrite-backend

- `seed.py` — seeds users/files into Appwrite.
- `appwrite-adapter.js` — adapts the frontend's expected API to Appwrite calls.

## frontend

Serve the folder over `http://` (e.g. `python -m http.server`) and open `index.html`. Use the toggle to switch between Mock, Django, and Appwrite backends.

- `mock-api.js` — in-browser mock that reads `seed-data.json`.
- `seed-data.json` — demo users/files shared by the mock, the quick-fill buttons, and the Django `seed_users` command.