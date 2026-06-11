from rest_framework import serializers
from apps.base.serializers.company_serializer import CompanyLookUpSerializer
from apps.base.models.company_model import Company


class AssociateCompanyField(serializers.IntegerField):

    def to_representation(self, value):
        if not isinstance(value, Company):
            value = Company.objects.filter(id=value).first()
        serializer = CompanyLookUpSerializer(value)
        return serializer.data
