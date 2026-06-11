from rest_framework import serializers


class CheckForceUpdateSerializer(serializers.Serializer):
    app_version = serializers.CharField(required=True)
    platform = serializers.ChoiceField(
        choices=["ios", "android"],
        required=True,
    )
