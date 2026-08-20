from rest_framework import serializers
from .models import File


class FileSerializer(serializers.ModelSerializer):
    class Meta:
        model = File
        fields = ["id", "filename", "mime_type", "size_bytes", "uploaded_at"]