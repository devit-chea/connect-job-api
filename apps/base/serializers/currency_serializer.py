from rest_framework import serializers
from apps.base.models.currency_model import Currency


class CurrencyInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ["id", "name", "code"]


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = "__all__"
