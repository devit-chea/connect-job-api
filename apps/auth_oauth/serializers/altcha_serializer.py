from rest_framework import serializers


class AltchaChallengeSerializer(serializers.Serializer):
    algorithm = serializers.CharField(
        help_text="The hashing algorithm used (e.g., 'SHA-256')."
    )
    challenge = serializers.CharField(
        help_text="The hashed challenge string for the client to solve."
    )
    max_number = serializers.IntegerField(
        help_text="The maximum number (difficulty target) for the Proof-of-Work."
    )
    salt = serializers.CharField(
        help_text="The unique salt string, which includes the expiration time."
    )
    signature = serializers.CharField(
        help_text="The HMAC signature used to verify the integrity of the challenge."
    )
