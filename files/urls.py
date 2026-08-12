from django.urls import path
from .views import FileListView, FileDetailView, FileDownloadView

urlpatterns = [
    path("files", FileListView.as_view(), name="file-list"),
    path("files/<int:pk>", FileDetailView.as_view(), name="file-detail"),
    path("files/<int:pk>/download", FileDownloadView.as_view(), name="file-download"),
]