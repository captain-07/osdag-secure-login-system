from rest_framework import serializers
from .models import File


class FileSerializer(serializers.ModelSerializer):
    class Meta:
        model = File
        # Deliberately not including `file` (the path) or `owner` here —
        # the client gets metadata only; actual bytes come through the
        # dedicated download endpoint below.
        fields = ["id", "filename", "mime_type", "size_bytes", "uploaded_at"]