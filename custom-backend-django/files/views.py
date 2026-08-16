from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import FileResponse
from .models import File
from .serializers import FileSerializer


class FileListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Filtering at the queryset level (not "get all, then filter in
        # Python") means the DB itself never returns another user's rows.
        # Wrapped in {"files": [...]} to match the mock and Appwrite
        # backends, which the provided client expects.
        queryset = File.objects.filter(owner=request.user)
        return Response({"files": FileSerializer(queryset, many=True).data})


def _get_owned_or_error(pk, user):
    """
    Shared lookup for detail + download views — keeps the 404-vs-403 logic
    in one place instead of duplicating it (and risking the two endpoints
    drifting apart).
    Returns (file_obj, None) on success, or (None, Response) on failure.
    """
    try:
        f = File.objects.get(pk=pk)
    except File.DoesNotExist:
        return None, Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if f.owner_id != user.id:
        # File exists, but not yours — 403, deliberately distinct from 404.
        return None, Response({"detail": "You do not have access to this file."}, status=status.HTTP_403_FORBIDDEN)

    return f, None


class FileDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        f, error = _get_owned_or_error(pk, request.user)
        if error:
            return error
        return Response(FileSerializer(f).data)


class FileDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        f, error = _get_owned_or_error(pk, request.user)
        if error:
            return error
        # as_attachment=True triggers a download rather than an inline
        # render — matches what the frontend's downloadFileById() expects
        # (it blob()s the response and forces a save-as).
        return FileResponse(f.file.open("rb"), as_attachment=True, filename=f.filename)