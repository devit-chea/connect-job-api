from rest_framework import serializers
from apps.base.models.country_model import Country


class CountryViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = "__all__"


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ["id", "code2", "code3", "country", "country_kh", "nationality"]
        extra_kwargs = {
            "code2": {"required": False},
            "id": {"required": False},
            "code3": {"required": False},
            "country": {"required": False},
            "country_kh": {"required": False},
        }


class NationalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ["id", "code2", "code3", "nationality"]
        extra_kwargs = {
            "code2": {"required": False},
            "id": {"required": False},
            "code3": {"required": False},
            "nationality": {"required": False},
        }


class CountryInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ["id", "country", "country_kh"]


class NationalityInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ["id", "nationality"]
