"""Login rate-limiting tests."""

import pytest

from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.throttling import SimpleRateThrottle

pytestmark = pytest.mark.django_db

LOGIN_URL = reverse("login")

_RATE_KEY = "login"
_ORIGINAL_RATE = SimpleRateThrottle.THROTTLE_RATES[_RATE_KEY]


@pytest.fixture(autouse=True)
def tight_login_throttle():
    SimpleRateThrottle.THROTTLE_RATES[_RATE_KEY] = "2/min"
    yield
    SimpleRateThrottle.THROTTLE_RATES[_RATE_KEY] = _ORIGINAL_RATE


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def test_login_is_throttled_after_limit(api_client, user):
    payload = {"email": "alice@example.com", "password": "wrong-pass"}

    for _ in range(2):
        resp = api_client.post(LOGIN_URL, payload, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    resp = api_client.post(LOGIN_URL, payload, format="json")
    assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS


def test_throttle_is_per_ip(api_client, user):
    payload = {"email": "alice@example.com", "password": "wrong-pass"}

    for _ in range(2):
        resp = api_client.post(
            LOGIN_URL, payload, format="json", REMOTE_ADDR="1.2.3.4"
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    resp = api_client.post(LOGIN_URL, payload, format="json", REMOTE_ADDR="1.2.3.4")
    assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    resp = api_client.post(LOGIN_URL, payload, format="json", REMOTE_ADDR="5.6.7.8")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED