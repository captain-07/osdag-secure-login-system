"""Registration, login, lockout, and /me tests."""

from datetime import timedelta

import pytest

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

pytestmark = pytest.mark.django_db

REGISTER_URL = reverse("register")
LOGIN_URL = reverse("login")
ME_URL = reverse("me")


def test_register_creates_user(api_client):
    resp = api_client.post(
        REGISTER_URL,
        {"email": "new@example.com", "password": "Password123!"},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    assert "password" not in resp.data
    assert get_user_model().objects.filter(email="new@example.com").exists()


def test_register_rejects_weak_password(api_client):
    resp = api_client.post(
        REGISTER_URL,
        {"email": "weak@example.com", "password": "123"},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_login_success(api_client, user):
    resp = api_client.post(
        LOGIN_URL,
        {"email": "alice@example.com", "password": "Password123!"},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    assert "access" in resp.data
    assert "refresh" in resp.data
    assert resp.data["user"]["email"] == "alice@example.com"


def test_login_wrong_password_returns_generic_error(api_client, user):
    resp = api_client.post(
        LOGIN_URL,
        {"email": "alice@example.com", "password": "wrong-pass"},
        format="json",
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp.data["detail"] == "Invalid email or password."


def test_login_unknown_email_returns_same_error(api_client):
    resp = api_client.post(
        LOGIN_URL,
        {"email": "ghost@example.com", "password": "Password123!"},
        format="json",
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp.data["detail"] == "Invalid email or password."


def test_me_returns_profile(auth_client, user):
    resp = auth_client.get(ME_URL)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["email"] == user.email


def test_me_requires_authentication(api_client):
    resp = api_client.get(ME_URL)
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_account_locks_after_five_failed_attempts(api_client, user):
    for _ in range(5):
        resp = api_client.post(
            LOGIN_URL,
            {"email": "alice@example.com", "password": "wrong-pass"},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    user.refresh_from_db()
    assert user.failed_login_attempts == 5
    assert user.is_locked()

    resp = api_client.post(
        LOGIN_URL,
        {"email": "alice@example.com", "password": "Password123!"},
        format="json",
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_lockout_budget_resets_after_window_expires(api_client, user):
    user.failed_login_attempts = 5
    user.locked_until = timezone.now() - timedelta(seconds=1)
    user.save(update_fields=["failed_login_attempts", "locked_until"])

    resp = api_client.post(
        LOGIN_URL,
        {"email": "alice@example.com", "password": "wrong-pass"},
        format="json",
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    user.refresh_from_db()
    assert user.failed_login_attempts == 1
    assert user.locked_until is None
    assert not user.is_locked()


def test_inactive_user_cannot_login(api_client, user):
    user.is_active = False
    user.save(update_fields=["is_active"])

    resp = api_client.post(
        LOGIN_URL,
        {"email": "alice@example.com", "password": "Password123!"},
        format="json",
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
    assert resp.data["detail"] == "Invalid email or password."