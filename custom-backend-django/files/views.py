from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import FileResponse
from .models import File
from .serializers import FileSerializer


class FileListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
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
        return FileResponse(f.file.open("rb"), as_attachment=True, filename=f.filename)