"""Shared fixtures for the whole test suite.

Everything here is intentionally environment-agnostic: it swaps the Django
settings used by pytest onto SQLite + an in-memory cache, so `pytest` works
out of the box without a local PostgreSQL server or Redis running.
"""

import os
import tempfile

import pytest

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


# Make config.settings importable even when custom-backend-django/.env is
# absent (e.g. on a fresh clone that only has .env.example). These defaults
# are overridden below anyway — they only exist so the settings module loads.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DB_NAME", "osdag_test")
os.environ.setdefault("DB_USER", "postgres")
os.environ.setdefault("DB_PASSWORD", "")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")


def pytest_configure(config):
    """Point the test run at SQLite + locmem cache before Django sets up."""
    from django.conf import settings

    # Update the existing dicts in place — Django's ConnectionHandler captured
    # a reference to them at import time, so replacing the dict objects would
    # drop the defaults it already injected (ATOMIC_REQUESTS, TIMEOUT, ...).
    settings.DATABASES["default"].update(
        {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    )
    settings.CACHES["default"].update(
        {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "osdag-test",
        }
    )
    settings.MEDIA_ROOT = tempfile.mkdtemp(prefix="osdag-test-media-")

    # Give non-throttle tests headroom so lockout/me/login logic isn't
    # fighting the rate limiter. The throttle test overrides this itself.
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
        "login": "100/min",
        "anon": "100/min",
    }


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(
        email="alice@example.com",
        password="Password123!",
    )


@pytest.fixture
def auth_client(db, user):
    """An APIClient already authenticated as `user` via a valid JWT."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client