from rest_framework import serializers

class TokenExchangeSerializer(serializers.Serializer):
    temporary_code = serializers.CharField()
    state = serializers.CharField()
    authorization_code = serializers.CharField()
