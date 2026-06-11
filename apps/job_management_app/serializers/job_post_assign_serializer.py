from rest_framework import serializers

from apps.base.utils.file_management_util import FileURLService, _to_uuid
from apps.job_management_app.models.job_post_assigned_recruiter_model import JobPostAssignedRecruiterModel


class CompanyRecruiterPickerSerializer(serializers.Serializer):
    """
    Lightweight read-only serializer for the recruiter assignment picker
    """
    ucp_id = serializers.IntegerField(source="id")
    full_name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    current_position = serializers.SerializerMethodField()
    profile_image_url = serializers.SerializerMethodField()

    def _profile(self, obj):
        return getattr(obj, "profile", None)

    def get_full_name(self, obj):
        p = self._profile(obj)
        return p.full_name if p else None

    def get_email(self, obj):
        p = self._profile(obj)
        return p.email if p else None

    def get_current_position(self, obj):
        p = self._profile(obj)
        return p.current_position if p else None

    def get_profile_image_url(self, obj):
        p = self._profile(obj)
        if not p or not p.profile_picture_id:
            return None
        pid = _to_uuid(p.profile_picture_id)
        if not pid:
            return None
        file_map = FileURLService.map_by_file_ids([pid])
        return (file_map.get(pid) or {}).get("file_path")

class AssignedRecruiterInfoSerializer(serializers.ModelSerializer):
    ucp_id = serializers.IntegerField(source="assigned_ucp_id", read_only=True)
    full_name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    current_position = serializers.SerializerMethodField()
    profile_image_url = serializers.SerializerMethodField()
    assigned_by_ucp_id = serializers.CharField(source="create_ucp_id", read_only=True)

    class Meta:
        model = JobPostAssignedRecruiterModel
        fields = [
            "id",
            "ucp_id",
            "full_name",
            "email",
            "current_position",
            "profile_image_url",
            "assigned_by_ucp_id",
            "create_date",
        ]

    def _get_profile(self, obj):
        ucp = obj.assigned_ucp
        return ucp.profile if ucp else None

    def get_full_name(self, obj):
        profile = self._get_profile(obj)
        return profile.full_name if profile else None

    def get_email(self, obj):
        profile = self._get_profile(obj)
        return profile.email if profile else None

    def get_current_position(self, obj):
        profile = self._get_profile(obj)
        return profile.current_position if profile else None

    def get_profile_image_url(self, obj):
        profile = self._get_profile(obj)
        if not profile or not profile.profile_picture_id:
            return None
        pid = _to_uuid(profile.profile_picture_id)
        if not pid:
            return None
        file_map = FileURLService.map_by_file_ids([pid])
        return (file_map.get(pid) or {}).get("file_path")


class AssignRecruitersSerializer(serializers.Serializer):
    ucp_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=50,
    )
