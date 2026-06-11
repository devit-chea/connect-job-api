from apps.base.models.language_model import Language
from apps.base.serializers.language_serializer import LanguageSerializer
from apps.base.views.base_views import BaseModelViewSet


class LanguageView(BaseModelViewSet):
    search_fields = ["id", "name", "code", "iso_code", "url_code"]
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer
