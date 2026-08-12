from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("api/", include("accounts.urls")),
    path("api/", include("files.urls")),
]

if settings.DEBUG:
    # Serves uploaded files from MEDIA_ROOT during local dev only —
    # never used in production (a real deploy serves media via nginx/S3).
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)