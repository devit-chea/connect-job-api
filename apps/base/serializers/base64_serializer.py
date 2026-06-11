from rest_framework import serializers


class Base64FileSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    file_name = serializers.CharField(read_only=True)
    file_url = serializers.SerializerMethodField()
    image_thumbnail_url = serializers.SerializerMethodField()
    ref_type = serializers.CharField(read_only=True)
    ref_id = serializers.CharField(read_only=True)
    file_size = serializers.CharField(read_only=True)
    is_deleted = serializers.BooleanField(read_only=True)

    def get_file_url(self, obj):
        file_url = obj.file.url
        return file_url if getattr(obj, "file", None) else None

    def get_image_thumbnail_url(self, obj):
        return (
            obj.image_thumbnail.url if getattr(obj, "image_thumbnail", None) else None
        )
