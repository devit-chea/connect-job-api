from rest_framework import filters

from apps.base.views.base_views import BaseModelViewSet
from apps.configuration.models.applicant_config_model import ApplicantConfig
from apps.configuration.serializers.applicant_config_serializer import ApplicantConfigSerializer


class ApplicantConfigView(BaseModelViewSet):
    permission_classes = ()
    queryset = ApplicantConfig.objects.all()
    serializer_class = ApplicantConfigSerializer

    queryset = ApplicantConfig.objects.all().order_by('-id')
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['value']
    filter_fields = ['field_name']
    ordering_fields = ['id']

    def get_queryset(self):
        queryset = super().get_queryset()
        field_name = self.request.query_params.get("field_name")
        if field_name:
            queryset = queryset.filter(field_name=field_name)
        return queryset

