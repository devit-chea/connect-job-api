from apps.auth_oauth.models.profile_model import Profile
from apps.base.serializers.base_serializer import BaseSerializer

class UserProfileSerializer(BaseSerializer):
    class Meta:
        model = Profile
        fields = "__all__"
