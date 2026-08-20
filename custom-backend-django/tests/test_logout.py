"""Logout + token-revocation tests."""

import pytest

from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

LOGOUT_URL = reverse("logout")
ME_URL = reverse("me")


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def test_logout_returns_205(auth_client):
    resp = auth_client.post(LOGOUT_URL, {}, format="json")
    assert resp.status_code == status.HTTP_205_RESET_CONTENT


def test_logout_requires_authentication(api_client):
    resp = api_client.post(LOGOUT_URL, {}, format="json")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_logout_revokes_access_token(db, user):
    refresh = RefreshToken.for_user(user)
    access = str(refresh.access_token)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    assert client.get(ME_URL).status_code == status.HTTP_200_OK

    resp = client.post(LOGOUT_URL, {"refresh": str(refresh)}, format="json")
    assert resp.status_code == status.HTTP_205_RESET_CONTENT

    assert client.get(ME_URL).status_code == status.HTTP_401_UNAUTHORIZED