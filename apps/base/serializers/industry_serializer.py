from rest_framework import serializers

from apps.base.models.industry_model import IndustryModel


class IndustrySerializer(serializers.ModelSerializer):
    class Meta:
        model = IndustryModel
        fields = ["id", "name", "description", "create_date"]