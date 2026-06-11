from apps.base.views.base_views import BaseModelViewSet
from apps.base.models.country_model import Country
from apps.base.serializers.country_serializer import CountrySerializer


class CountryView(BaseModelViewSet):
    queryset = Country.objects.all()
    serializer_class = CountrySerializer
    filterset_fields = ["code2", "code3", "country", "country_kh", "nationality"]
    search_fields = ["code2", "code3", "country", "country_kh", "nationality"]
