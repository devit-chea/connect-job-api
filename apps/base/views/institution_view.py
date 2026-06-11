from apps.base.views.base_views import BaseModelViewSet
from apps.base.models.institution_model import Institution
from apps.base.serializers.institution_serializer import InstitutionSerializer


class InstitutionView(BaseModelViewSet):
    search_fields = ["id", "name", "logo_url", "description"]
    queryset = Institution.objects.all()
    serializer_class = InstitutionSerializer
