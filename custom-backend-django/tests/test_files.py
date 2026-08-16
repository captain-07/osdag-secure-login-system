"""File list/detail/download and ownership-isolation tests."""

import pytest

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.urls import reverse
from rest_framework import status

from files.models import File

pytestmark = pytest.mark.django_db

LIST_URL = reverse("file-list")


@pytest.fixture
def owned_file(db, user):
    return File.objects.create(
        owner=user,
        filename="resume.pdf",
        file=ContentFile(b"%PDF-1.4 fake content", name="resume.pdf"),
        mime_type="application/pdf",
        size_bytes=19,
    )


@pytest.fixture
def other_user_file(db, user):
    other = get_user_model().objects.create_user(
        email="bob@example.com",
        password="Password123!",
    )
    return File.objects.create(
        owner=other,
        filename="secret.txt",
        file=ContentFile(b"top secret", name="secret.txt"),
        mime_type="text/plain",
        size_bytes=10,
    )


def test_list_files_returns_only_own(auth_client, owned_file, other_user_file):
    resp = auth_client.get(LIST_URL)
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.data["files"]) == 1
    assert resp.data["files"][0]["filename"] == "resume.pdf"


def test_file_detail_returns_own(auth_client, owned_file):
    resp = auth_client.get(reverse("file-detail", args=[owned_file.pk]))
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["filename"] == "resume.pdf"


def test_file_detail_of_other_user_is_403(auth_client, other_user_file):
    resp = auth_client.get(reverse("file-detail", args=[other_user_file.pk]))
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_file_detail_missing_is_404(auth_client):
    resp = auth_client.get(reverse("file-detail", args=[99999]))
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_file_download_streams_content(auth_client, owned_file):
    resp = auth_client.get(reverse("file-download", args=[owned_file.pk]))
    assert resp.status_code == status.HTTP_200_OK
    assert resp["Content-Disposition"].startswith("attachment")
    assert b"fake" in b"".join(resp.streaming_content)


def test_file_download_of_other_user_is_403(auth_client, other_user_file):
    resp = auth_client.get(reverse("file-download", args=[other_user_file.pk]))
    assert resp.status_code == status.HTTP_403_FORBIDDEN